"""
Settings dialog for RTMP Virtual Camera.

Provides a Tkinter-based UI for configuring application settings such as
protocol, ports, video dimensions, and reconnection behavior.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Optional, Callable

from .config_manager import AppConfig, ProtocolType, ConfigurationManager

log = logging.getLogger(__name__)


class SettingsDialog:
    """
    Tkinter-based settings dialog for configuring the application.
    """

    def __init__(
        self, 
        current_config: AppConfig, 
        on_save: Callable[[AppConfig], None],
        on_close: Optional[Callable[[], None]] = None
    ):
        """
        Initialize the settings dialog.
        
        Parameters
        ----------
        current_config : AppConfig
            The current application configuration
        on_save : callable
            Callback invoked when the user clicks "Save"
        on_close : callable, optional
            Callback invoked when the dialog is closed
        """
        self._config = current_config
        self._on_save = on_save
        self._on_close = on_close
        
        self._root: Optional[tk.Tk] = None
        
        # UI Variable storage
        self._protocol_var: tk.StringVar = None
        self._rtmp_port_var: tk.StringVar = None
        self._srt_port_var: tk.StringVar = None
        self._http_port_var: tk.StringVar = None
        self._width_var: tk.StringVar = None
        self._height_var: tk.StringVar = None
        self._fps_var: tk.StringVar = None
        self._auto_reconnect_var: tk.BooleanVar = None
        self._max_attempts_var: tk.StringVar = None

    def show(self) -> None:
        """Create and show the settings window."""
        self._root = tk.Tk()
        self._root.title("Local Virtual Camera Settings")
        self._root.geometry("400x550")
        self._root.resizable(False, False)
        self._root.configure(bg="#16161e")
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#16161e")
        style.configure("TLabel", background="#16161e", foreground="#e0e0e8", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TCheckbutton", background="#16161e", foreground="#e0e0e8")
        
        main_frame = ttk.Frame(self._root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ── Protocol Selection ─────────────────────────────────
        ttk.Label(main_frame, text="Streaming Protocol:", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        self._protocol_var = tk.StringVar(value=self._config.protocol.value)
        protocols = [p.value for p in ProtocolType]
        protocol_combo = ttk.Combobox(main_frame, textvariable=self._protocol_var, values=protocols, state="readonly")
        protocol_combo.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 20))
        
        # ── Port Configuration ────────────────────────────────
        ttk.Label(main_frame, text="Network Ports:", font=("Segoe UI", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=(0, 10))
        
        # RTMP Port
        ttk.Label(main_frame, text="RTMP Port:").grid(row=3, column=0, sticky=tk.W)
        self._rtmp_port_var = tk.StringVar(value=str(self._config.rtmp_port))
        ttk.Entry(main_frame, textvariable=self._rtmp_port_var).grid(row=3, column=1, sticky=tk.EW, pady=5)
        
        # SRT Port
        ttk.Label(main_frame, text="SRT Port:").grid(row=4, column=0, sticky=tk.W)
        self._srt_port_var = tk.StringVar(value=str(self._config.srt_port))
        ttk.Entry(main_frame, textvariable=self._srt_port_var).grid(row=4, column=1, sticky=tk.EW, pady=5)
        
        # HTTP Port
        ttk.Label(main_frame, text="HTTP Info Port:").grid(row=5, column=0, sticky=tk.W)
        self._http_port_var = tk.StringVar(value=str(self._config.http_port))
        ttk.Entry(main_frame, textvariable=self._http_port_var).grid(row=5, column=1, sticky=tk.EW, pady=(5, 20))
        
        # ── Video Settings ───────────────────────────────────
        ttk.Label(main_frame, text="Video Quality:", font=("Segoe UI", 10, "bold")).grid(row=6, column=0, sticky=tk.W, pady=(0, 10))
        
        # Width
        ttk.Label(main_frame, text="Width (px):").grid(row=7, column=0, sticky=tk.W)
        self._width_var = tk.StringVar(value=str(self._config.frame_width))
        ttk.Entry(main_frame, textvariable=self._width_var).grid(row=7, column=1, sticky=tk.EW, pady=5)
        
        # Height
        ttk.Label(main_frame, text="Height (px):").grid(row=8, column=0, sticky=tk.W)
        self._height_var = tk.StringVar(value=str(self._config.frame_height))
        ttk.Entry(main_frame, textvariable=self._height_var).grid(row=8, column=1, sticky=tk.EW, pady=5)
        
        # FPS
        ttk.Label(main_frame, text="Target FPS:").grid(row=9, column=0, sticky=tk.W)
        self._fps_var = tk.StringVar(value=str(self._config.fps))
        ttk.Entry(main_frame, textvariable=self._fps_var).grid(row=9, column=1, sticky=tk.EW, pady=(5, 20))
        
        # ── Reconnection ──────────────────────────────────────
        ttk.Label(main_frame, text="Reconnection:", font=("Segoe UI", 10, "bold")).grid(row=10, column=0, sticky=tk.W, pady=(0, 10))
        
        self._auto_reconnect_var = tk.BooleanVar(value=self._config.auto_reconnect)
        ttk.Checkbutton(main_frame, text="Enable Auto-reconnect", variable=self._auto_reconnect_var).grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(main_frame, text="Max Attempts:").grid(row=12, column=0, sticky=tk.W)
        self._max_attempts_var = tk.StringVar(value=str(self._config.max_reconnect_attempts))
        ttk.Entry(main_frame, textvariable=self._max_attempts_var).grid(row=12, column=1, sticky=tk.EW, pady=5)
        
        # ── Buttons ──────────────────────────────────────────
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=13, column=0, columnspan=2, pady=(30, 0), sticky=tk.E)
        
        ttk.Button(button_frame, text="Cancel", command=self._on_cancel_btn).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Settings", command=self._on_save_btn).pack(side=tk.LEFT, padx=5)
        
        # Center on screen
        self._root.update_idletasks()
        w, h = self._root.winfo_width(), self._root.winfo_height()
        x = (self._root.winfo_screenwidth() - w) // 2
        y = (self._root.winfo_screenheight() - h) // 2
        self._root.geometry(f"+{x}+{y}")
        self._root.attributes("-topmost", True)
        
        self._root.protocol("WM_DELETE_WINDOW", self._on_cancel_btn)
        self._root.mainloop()

    def _on_save_btn(self) -> None:
        """Validate and save settings."""
        try:
            # Create a new config object from UI variables
            new_config = AppConfig(
                protocol=ProtocolType(self._protocol_var.get()),
                rtmp_port=int(self._rtmp_port_var.get()),
                srt_port=int(self._srt_port_var.get()),
                http_port=int(self._http_port_var.get()),
                frame_width=int(self._width_var.get()),
                frame_height=int(self._height_var.get()),
                fps=int(self._fps_var.get()),
                auto_reconnect=self._auto_reconnect_var.get(),
                max_reconnect_attempts=int(self._max_attempts_var.get())
            )
            
            # Validate using ConfigurationManager logic
            mgr = ConfigurationManager()
            is_valid, error = mgr.validate(new_config)
            
            if not is_valid:
                messagebox.showerror("Invalid Settings", f"Validation failed: {error}")
                return
            
            # Invoke save callback
            self._on_save(new_config)
            
            # Close window
            self._root.destroy()
            if self._on_close:
                self._on_close()
                
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input value: {e}. Please ensure ports and dimensions are numbers.")
        except Exception as e:
            log.exception("Failed to save settings")
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def _on_cancel_btn(self) -> None:
        """Close without saving."""
        self._root.destroy()
        if self._on_close:
            self._on_close()
