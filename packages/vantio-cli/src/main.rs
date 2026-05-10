use std::env;
use std::process::{Command, Stdio};
use std::time::{SystemTime, UNIX_EPOCH};

fn main() {
    // 1. Parse execution arguments
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 || args[1] != "run" {
        eprintln!("VANTIO_FATAL: Invalid execution syntax.");
        eprintln!("USAGE: vantio run <command> [args...]");
        eprintln!("EXAMPLE: vantio run node server.js");
        std::process::exit(1);
    }

    // 2. Generate Deterministic Trace ID
    let start_time = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let trace_id = format!("VANTIO_TRACE_{}", start_time);

    // 3. Mathematical Enforcement of the Schism
    // We explicitly log that this is user-space, NOT Ring-0 eBPF.
    println!("==================================================");
    println!("∅ VANTIO TIER-01: USER-SPACE INTERCEPTION ACTIVE");
    println!("TRACE_ID: {}", trace_id);
    println!("MODE: Synchronous Wrapper (Zero-Line Visibility)");
    println!("==================================================\n");

    let target_cmd = &args[2];
    let target_args = &args[3..];

    // 4. Inject Trace ID and spawn the target process
    let mut child = Command::new(target_cmd)
        .args(target_args)
        .env("VANTIO_TRACE_ID", &trace_id)
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("VANTIO_FATAL: Failed to execute wrapped process. Verify your target command.");

    // 5. Await process completion
    let status = child
        .wait()
        .expect("VANTIO_FATAL: Process wait state fractured.");

    println!("\n==================================================");
    println!("∅ VANTIO TIER-01: EXECUTION TERMINATED");
    println!("STATUS: {}", status);
    println!("==================================================");

    if !status.success() {
        std::process::exit(status.code().unwrap_or(1));
    }
}
