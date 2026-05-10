use std::env;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 || args[1] != "run" {
        eprintln!("VANTIO: Invalid execution syntax.");
        eprintln!("USAGE: vantio run <command> [args...]");
        std::process::exit(1);
    }

    let start_time = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let trace_id = format!("VANTIO_TRACE_{}", start_time);

    let cloud_ingest = env::var("VANTIO_CLOUD_INGEST").unwrap_or_else(|_| "false".to_string());
    let is_cloud_active = cloud_ingest == "true";

    println!("==================================================");
    println!("VANTIO TIER-01: USER-SPACE INTERCEPTION ACTIVE");
    println!("TRACE_ID: {}", trace_id);

    if is_cloud_active {
        if env::var("VANTIO_API_KEY").is_err() {
            eprintln!("WARNING: VANTIO_CLOUD_INGEST is active, but VANTIO_API_KEY is missing.");
            eprintln!("Telemetry transmission to the Managed Edge Proxy will fail.");
        }
        println!("ROUTING: Asynchronous Cloud Ingestion (Tier-2 Proxy)");
    } else {
        println!("ROUTING: Ephemeral Local Substrate (SQLite)");
    }
    println!("==================================================\n");

    let target_cmd = &args[2];
    let target_args = &args[3..];

    let mut child = Command::new(target_cmd)
        .args(target_args)
        .env("VANTIO_TRACE_ID", &trace_id)
        .env("VANTIO_CLOUD_INGEST", &cloud_ingest)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("VANTIO_FATAL: Failed to execute wrapped process. Verify your target command.");

    let status = child
        .wait()
        .expect("VANTIO_FATAL: Process wait state fractured.");

    println!("\n==================================================");
    println!("VANTIO TIER-01: EXECUTION TERMINATED");
    println!("STATUS: {}", status);
    println!("==================================================");

    if !status.success() {
        std::process::exit(status.code().unwrap_or(1));
    }
}
