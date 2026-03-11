use std::io::{BufRead, BufReader};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use tokio::time::{sleep, Duration};

pub struct WorkerProcess {
    child: Option<Child>,
    pub port: Option<u16>,
}

impl WorkerProcess {
    pub fn new() -> Self {
        WorkerProcess { child: None, port: None }
    }

    pub fn spawn(&mut self, ml_worker_path: &str) -> anyhow::Result<u16> {
        log::info!("Spawning Python ML worker: {}", ml_worker_path);

        // Find venv Python relative to ml-worker path
        let ml_worker_dir = std::path::Path::new(ml_worker_path).parent()
            .map(|p| p.to_path_buf())
            .unwrap_or_default();
        let venv_python = ml_worker_dir
            .join(".venv")
            .join("bin")
            .join("python");

        let python_cmd = if venv_python.exists() {
            venv_python.to_string_lossy().to_string()
        } else {
            "python3".to_string()
        };

        let mut child = Command::new(&python_cmd)
            .args([ml_worker_path])
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit())
            .spawn()
            .map_err(|e| anyhow::anyhow!("Failed to spawn worker: {}", e))?;

        let stdout = child.stdout.take().ok_or_else(|| anyhow::anyhow!("No stdout"))?;
        let reader = BufReader::new(stdout);

        let port = read_port_from_stdout(reader)?;
        log::info!("Worker started on port {}, waiting for server to be ready...", port);

        // Wait for the server to be ready (up to 5 seconds)
        let max_attempts = 50;
        for i in 0..max_attempts {
            std::thread::sleep(std::time::Duration::from_millis(100));
            if std::net::TcpStream::connect(format!("127.0.0.1:{}", port)).is_ok() {
                log::info!("Worker server is ready on port {}", port);
                break;
            }
            if i == max_attempts - 1 {
                return Err(anyhow::anyhow!("Worker server did not become ready in time"));
            }
        }

        self.child = Some(child);
        self.port = Some(port);
        Ok(port)
    }

    pub fn kill(&mut self) {
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

impl Drop for WorkerProcess {
    fn drop(&mut self) {
        self.kill();
    }
}

fn read_port_from_stdout(reader: BufReader<impl std::io::Read>) -> anyhow::Result<u16> {
    for line in reader.lines().take(50) {
        let line = line?;
        log::debug!("Worker stdout: {}", line);
        if let Some(port_str) = line.strip_prefix("PORT=") {
            let port: u16 = port_str
                .trim()
                .parse()
                .map_err(|_| anyhow::anyhow!("Invalid port: {}", port_str))?;
            return Ok(port);
        }
    }
    Err(anyhow::anyhow!("Worker did not emit PORT= line within first 50 lines"))
}

pub async fn spawn_with_retry(
    ml_worker_path: String,
    worker_process: Arc<Mutex<WorkerProcess>>,
) -> anyhow::Result<u16> {
    let mut backoff_secs = 1u64;
    loop {
        let result = {
            let mut wp = worker_process.lock().unwrap();
            wp.spawn(&ml_worker_path)
        };

        match result {
            Ok(port) => return Ok(port),
            Err(e) => {
                log::error!("Worker spawn failed: {}. Retrying in {}s", e, backoff_secs);
                sleep(Duration::from_secs(backoff_secs)).await;
                backoff_secs = (backoff_secs * 2).min(30);
            }
        }
    }
}
