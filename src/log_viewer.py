"""
Log viewer and diagnostic export for RTMP Virtual Camera.

Provides a Tkinter-based UI for viewing recent application logs and 
a utility for exporting system diagnostic information.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import os
import platform
import json
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)


class LogViewer:
    """
    Tkinter-based log viewer window.
    """

    def __init__(self, log_file: Optional[str] = None):
        """
        Initialize the log viewer.
        
        Parameters
        ----------
        log_file : str, optional
            Path to the log file to display. If None, displays a message.
        """
        self._log_file = log_file
        self._root: Optional[tk.Tk] = None
        self._text_area: Optional[tk.Text] = None

    def show(self) -> None:
        """Create and show the log viewer window."""
        self._root = tk.Tk()
        self._root.title("Local Virtual Camera - Log Viewer")
        self._root.geometry("800x600")
        self._root.configure(bg="#16161e")
        
        main_frame = ttk.Frame(self._root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Log display area
        self._text_area = tk.Text(
            main_frame, 
            bg="#0d0d12", 
            fg="#e0e0e8", 
            insertbackground="white",
            font=("Consolas", 10),
            padx=10,
            pady=10
        )
        self._text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self._text_area.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._text_area.configure(yscrollcommand=scrollbar.set)
        
        # Control bar
        control_frame = ttk.Frame(self._root, padding="10")
        control_frame.pack(fill=tk.X)
        
        ttk.Button(control_frame, text="Refresh", command=self._load_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Logs...", command=self._export_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Export Diagnostics...", command=self._export_diagnostics).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Close", command=self._root.destroy).pack(side=tk.RIGHT, padx=5)
        
        self._load_logs()
        
        # Center on screen
        self._root.update_idletasks()
        w, h = self._root.winfo_width(), self._root.winfo_height()
        x = (self._root.winfo_screenwidth() - w) // 2
        y = (self._root.winfo_screenheight() - h) // 2
        self._root.geometry(f"+{x}+{y}")
        
        self._root.mainloop()

    def _load_logs(self) -> None:
        """Load logs from file into text area."""
        self._text_area.delete(1.0, tk.END)
        
        if not self._log_file or not os.path.exists(self._log_file):
            self._text_area.insert(tk.END, "Log file not found or not configured.")
            return
            
        try:
            with open(self._log_file, "r", encoding="utf-8") as f:
                # Read last 1000 lines for performance
                lines = f.readlines()[-1000:]
                self._text_area.insert(tk.END, "".join(lines))
                self._text_area.see(tk.END)
        except Exception as e:
            self._text_area.insert(tk.END, f"Error loading logs: {e}")

    def _export_logs(self) -> None:
        """Save current logs to a file."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt")],
            initialfile=f"vcam_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        if not file_path:
            return
            
        try:
            logs = self._text_area.get(1.0, tk.END)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(logs)
            messagebox.showinfo("Export Successful", f"Logs exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export logs: {e}")

    def _export_diagnostics(self) -> None:
        """Generate and save diagnostic information."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile=f"vcam_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        if not file_path:
            return
            
        try:
            diag_info = {
                "timestamp": datetime.now().isoformat(),
                "os": {
                    "system": platform.system(),
                    "release": platform.release(),
                    "version": platform.version(),
                    "machine": platform.machine(),
                    "processor": platform.processor()
                },
                "python": {
                    "version": platform.python_version(),
                    "implementation": platform.python_implementation()
                }
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(diag_info, f, indent=4)
            messagebox.showinfo("Export Successful", f"Diagnostics exported to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to export diagnostics: {e}")
