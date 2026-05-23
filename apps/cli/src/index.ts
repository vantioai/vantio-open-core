#!/usr/bin/env node
import { Command } from 'commander';
import { spawn } from 'child_process';
import * as crypto from 'crypto';

const program = new Command();

program
  .name('vantio')
  .description('Open-core CLI to seed VANTIO_TRACE_ID and spawn traced agents')
  .version('0.1.0');

program
  .command('run')
  .description('Run a command with a trace ID')
  .option('-t, --trace-id <id>', 'Trace ID (hex or decimal). Auto-generated if omitted.')
  .argument('<command...>', 'Command to run')
  .action((commandArgs, options) => {
    // 1. Generate or parse trace ID
    let traceIdStr = options.traceId;
    if (!traceIdStr) {
      // Generate a random 64-bit hex string
      traceIdStr = '0x' + crypto.randomBytes(8).toString('hex');
    }
    
    console.log(`[Vantio] Generated/Using Trace ID: ${traceIdStr}`);

    // 2. We need the PID of the process we are ABOUT to spawn, or our own PID.
    // Since we are in Windows (Ring-3) and the eBPF map is in WSL (Ring-0),
    // we must bridge the gap. We will spawn the child process, get its PID,
    // and then use WSL interop to inject the trace ID for that PID into the kernel map.
    
    // Note: If we are running a Windows executable, its PID won't mean anything to the WSL kernel.
    // This architecture assumes we are spawning a WSL process from Windows, OR
    // we are tracing Windows processes via a different mechanism.
    // Assuming we are spawning a WSL process for the LLM agent:
    
    const child = spawn('wsl.exe', ['-d', 'Ubuntu', '--', ...commandArgs], {
      stdio: 'inherit',
      env: { ...process.env, VANTIO_TRACE_ID: traceIdStr }
    });

    // We can't easily get the WSL PID of the child from the Windows side immediately.
    // The vantio-loader in WSL needs to be told about this trace ID.
    // A better approach: The WSL process itself should seed the map, or we use the loader's --inject flag.
    
    // For now, we rely on the VANTIO_TRACE_ID environment variable being passed through WSL.
    // If the spawned command is a script that reads VANTIO_TRACE_ID and calls `vantio-loader --inject`,
    // or if we just let the environment variable propagate.
    
    console.log(`[Vantio] Spawning WSL command: ${commandArgs.join(' ')}`);
    console.log(`[Vantio] Note: To strictly enforce the boundary, the WSL process must seed the map using this Trace ID.`);

    child.on('close', (code) => {
      process.exit(code ?? 0);
    });
  });

program.parse();
