import asyncio
import uvicorn
import os
import sys
import json
import logging
import subprocess
import fcntl
import struct
import termios

from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebShell")

app = FastAPI()

# 1. Mount Static & Templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, target: str = None, token: str = None):
    await websocket.accept()
    
    # 1. Validation: Ensure a target was provided
    if not target:
        await websocket.send_text("Error: No target element specified.\r\n")
        await websocket.close()
        return

    if not token:
        await websocket.send_text("Error: Auth Token is required.\r\n")
        await websocket.close()
        return
    
    # 2. Set up the Pseudo-Terminal (PTY)
    master_fd, slave_fd = os.openpty()

    # 3. Define the command to run
    # Note: Ensure ./cgxsh.py is executable (chmod +x cgxsh.py)

    # Create a private copy of environment variables for this process
    process_env = os.environ.copy()
    process_env["AUTH_TOKEN"] = token  # <--- INJECT TOKEN HERE
    process_env["TERM"] = "xterm-256color"

    command = [sys.executable, "./cgxsh.py", target] 

    # 4. Spawn the subprocess
    try:
        process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=process_env,
            preexec_fn=os.setsid, 
            close_fds=True 
        )
        logger.info(f"Subprocess started with PID: {process.pid}")
    except Exception as e:
        logger.error(f"Failed to start subprocess: {e}")
        await websocket.close()
        return

    # Close slave_fd in the parent
    os.close(slave_fd)

    # 5. Helper: Set PTY Window Size
    def set_winsize(fd, row, col, xpix=0, ypix=0):
        winsize = struct.pack("HHHH", row, col, xpix, ypix)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    # 6. Async Loop: Read from PTY -> Send to Browser
    async def pty_reader():
        loop = asyncio.get_running_loop()
        try:
            while True:
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                if not data:
                    break
                await websocket.send_text(data.decode('utf-8', errors='ignore'))
        except OSError:
            logger.info("PTY closed (process finished)")
        except Exception as e:
            logger.error(f"Reader Error: {e}")

    # 7. Async Loop: Read from Browser -> Write to PTY
    async def pty_writer():
        try:
            while True:
                message = await websocket.receive_text()
                try:
                    data = json.loads(message)
                    if isinstance(data, dict) and 'cols' in data and 'rows' in data:
                        set_winsize(master_fd, data['rows'], data['cols'])
                        continue
                except json.JSONDecodeError:
                    pass 
                os.write(master_fd, message.encode())
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"Writer Error: {e}")

    # 8. Lifecycle Management (The Fix!)
    reader_task = asyncio.create_task(pty_reader())
    writer_task = asyncio.create_task(pty_writer())

    # Wait until EITHER the process exits OR the browser disconnects
    done, pending = await asyncio.wait(
        [reader_task, writer_task], 
        return_when=asyncio.FIRST_COMPLETED
    )

    # --- CLEANUP PHASE ---
    logger.info("Session ending, cleaning up...")
    
    for task in pending:
        task.cancel()
    
    if process.poll() is None:
        process.terminate()
        try:
            await asyncio.sleep(0.1) 
            if process.poll() is None:
                process.kill()
        except Exception:
            pass
    
    exit_code = process.poll()
    
    # If script crashed/exited with error, tell the user why
    if exit_code != 0 and exit_code is not None:
        logger.warning(f"Process exited with error code: {exit_code}")
        error_msg = f"\r\n\r\n\x1b[31;1m[Process Exited with Error Code: {exit_code}]\x1b[0m\r\n"
        error_msg += "\x1b[31mPossible causes: Invalid Element/Serial, Auth Failure, or Script Crash.\x1b[0m\r\n"
        
        try:
            await websocket.send_text(error_msg)
            await asyncio.sleep(1.0) # Wait for browser to render
        except Exception:
            pass 

    try:
        os.close(master_fd)
    except OSError:
        pass 
    
    try:
        await websocket.close()
    except Exception:
        pass

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)