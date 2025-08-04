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


def clean_logs_directory(logger: logging.Logger):
    """Clean ALL existing log files from the logs directory on startup."""
    try:
        logs_dir = Path(__file__).parent / "logs"
        if not logs_dir.exists():
            logs_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created logs directory: {logs_dir}")
            return
        
        # Get ALL log files (including rotated ones with .1, .2, etc.)
        files_to_clean = list(logs_dir.glob("*.log*"))
        
        if not files_to_clean:
            logger.info("No existing log files to clean")
            return
        
        logger.info(f"Cleaning ALL existing log files from: {logs_dir}")
        logger.info(f"Found {len(files_to_clean)} log files to remove")
        
        cleaned_count = 0
        for file_path in files_to_clean:
            try:
                file_path.unlink()
                cleaned_count += 1
                logger.debug(f"Removed: {file_path.name}")
            except Exception as e:
                logger.warning(f"Could not remove {file_path}: {str(e)}")
        
        logger.info(f"Successfully cleaned {cleaned_count} log files from logs directory")
        
    except Exception as e:
        logger.error(f"Error cleaning logs directory: {str(e)}")


def kill_processes_on_port(port: int, logger: logging.Logger):
    """Kill processes using the specified port."""
    try:
        killed_processes = []
        
        # Find processes using the port
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                # Get connections directly from the process object
                connections = proc.connections()
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
    """Clean up only specific temporary files that may interfere with startup."""
    try:
        project_root = Path(__file__).parent.parent
        cleaned_count = 0
        
        # Only clean specific problematic temp files, not all Python cache
        specific_cleanup_paths = [
            project_root / ".pytest_cache",  # Test cache only
            project_root / "src" / "*.tmp",  # Temp files in src only
        ]
        
        # Clean specific directories/files only
        for cleanup_path in specific_cleanup_paths:
            if "*" in str(cleanup_path):
                # Handle glob patterns
                for file_path in cleanup_path.parent.glob(cleanup_path.name):
                    try:
                        if file_path.is_file():
                            file_path.unlink()
                            cleaned_count += 1
                        elif file_path.is_dir():
                            shutil.rmtree(file_path)
                            cleaned_count += 1
                    except Exception as e:
                        logger.debug(f"Could not remove {file_path}: {str(e)}")
            else:
                # Handle specific paths
                if cleanup_path.exists():
                    try:
                        if cleanup_path.is_file():
                            cleanup_path.unlink()
                            cleaned_count += 1
                        elif cleanup_path.is_dir():
                            shutil.rmtree(cleanup_path)
                            cleaned_count += 1
                    except Exception as e:
                        logger.debug(f"Could not remove {cleanup_path}: {str(e)}")
        
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
    clean_logs_directory(logger)
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
