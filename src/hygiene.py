#!/usr/bin/env python3
"""
Hygiene script for Pydantic-AI Multi-Agent System.
Handles cleanup tasks like log management and port cleanup.
"""

import os
import shutil
import subprocess
import signal
import psutil
from pathlib import Path
import logging
from datetime import datetime


def setup_logging():
    """Setup logging for the hygiene script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def clean_logs_directory(logs_dir: Path, logger: logging.Logger):
    """Clean the logs directory, keeping only recent logs if needed."""
    try:
        if logs_dir.exists():
            # Count files before cleanup
            file_count = len(list(logs_dir.glob('*')))
            
            if file_count > 0:
                logger.info(f"Cleaning logs directory: {logs_dir}")
                logger.info(f"Found {file_count} files to clean")
                
                # Remove all files in the logs directory
                for file_path in logs_dir.glob('*'):
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"Removed log file: {file_path}")
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
                        logger.debug(f"Removed log directory: {file_path}")
                
                logger.info(f"Successfully cleaned {file_count} items from logs directory")
            else:
                logger.info("Logs directory is already clean")
        else:
            # Create logs directory if it doesn't exist
            logs_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created logs directory: {logs_dir}")
            
    except Exception as e:
        logger.error(f"Error cleaning logs directory: {str(e)}")


def kill_processes_on_port(port: int, logger: logging.Logger):
    """Kill processes using the specified port."""
    try:
        killed_processes = []
        
        # Find processes using the port
        for proc in psutil.process_iter(['pid', 'name', 'connections']):
            try:
                connections = proc.info['connections']
                if connections:
                    for conn in connections:
                        if hasattr(conn, 'laddr') and conn.laddr and conn.laddr.port == port:
                            pid = proc.info['pid']
                            name = proc.info['name']
                            killed_processes.append(f"{name} (PID: {pid})")
                            
                            # Try graceful termination first
                            proc.terminate()
                            try:
                                proc.wait(timeout=3)
                            except psutil.TimeoutExpired:
                                # Force kill if graceful termination fails
                                proc.kill()
                                
                            logger.info(f"Killed process using port {port}: {name} (PID: {pid})")
                            
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                # Process might have disappeared or we don't have access
                continue
                
        if killed_processes:
            logger.info(f"Successfully killed {len(killed_processes)} processes on port {port}")
        else:
            logger.info(f"No processes found using port {port}")
            
    except Exception as e:
        logger.error(f"Error killing processes on port {port}: {str(e)}")
        # Fallback to system commands
        try:
            # Try using lsof and kill as fallback
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    subprocess.run(['kill', '-9', pid], timeout=5)
                    logger.info(f"Killed process PID {pid} using port {port} (fallback method)")
        except Exception as fallback_error:
            logger.warning(f"Fallback port cleanup also failed: {str(fallback_error)}")


def kill_streamlit_processes(logger: logging.Logger):
    """Kill any running Streamlit processes."""
    try:
        killed_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any('streamlit' in arg.lower() for arg in cmdline):
                    pid = proc.info['pid']
                    name = proc.info['name']
                    
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    
                    killed_count += 1
                    logger.info(f"Killed Streamlit process: {name} (PID: {pid})")
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        if killed_count == 0:
            logger.info("No Streamlit processes found running")
        else:
            logger.info(f"Successfully killed {killed_count} Streamlit processes")
            
    except Exception as e:
        logger.error(f"Error killing Streamlit processes: {str(e)}")


def cleanup_temp_files(logger: logging.Logger):
    """Clean up temporary files and caches."""
    try:
        temp_patterns = [
            "*.pyc",
            "__pycache__",
            "*.tmp",
            "*.log",
            ".pytest_cache"
        ]
        
        project_root = Path(__file__).parent.parent
        cleaned_count = 0
        
        for pattern in temp_patterns:
            for file_path in project_root.rglob(pattern):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        cleaned_count += 1
                    elif file_path.is_dir():
                        shutil.rmtree(file_path)
                        cleaned_count += 1
                except Exception as e:
                    logger.debug(f"Could not remove {file_path}: {str(e)}")
        
        if cleaned_count > 0:
            logger.info(f"Cleaned {cleaned_count} temporary files/directories")
        else:
            logger.info("No temporary files to clean")
            
    except Exception as e:
        logger.error(f"Error cleaning temporary files: {str(e)}")


def run_hygiene_tasks(logs_dir: str = None, port: int = 8501):
    """Run all hygiene tasks."""
    logger = setup_logging()
    logger.info("🧹 Starting hygiene cleanup tasks...")
    
    # Determine logs directory
    if logs_dir is None:
        logs_dir = Path(__file__).parent / "logs"
    else:
        logs_dir = Path(logs_dir)
    
    # Run cleanup tasks
    clean_logs_directory(logs_dir, logger)
    kill_processes_on_port(port, logger)
    kill_streamlit_processes(logger)
    cleanup_temp_files(logger)
    
    logger.info("✅ Hygiene cleanup completed successfully!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run hygiene cleanup tasks")
    parser.add_argument("--logs-dir", help="Path to logs directory to clean")
    parser.add_argument("--port", type=int, default=8501, help="Port to clean (default: 8501)")
    
    args = parser.parse_args()
    
    run_hygiene_tasks(logs_dir=args.logs_dir, port=args.port)
