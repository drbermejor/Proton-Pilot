#!/usr/bin/env python3
"""Select and terminate hung user processes and their descendants."""

from __future__ import annotations

import os
import queue
import signal
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox, ttk


PROTECTED_NAMES = {
    "systemd",
    "(sd-pam)",
    "dbus-daemon",
    "dbus-broker",
    "kwin_wayland",
    "plasmashell",
    "kded6",
    "Xwayland",
    "pipewire",
    "wireplumber",
}

# Blocked, zombie, stopped/traced, or dead process states.
PROBLEM_STATES = {"D", "Z", "T", "t", "X", "x"}


def process_rows() -> list[dict[str, object]]:
    command = [
        "ps",
        "-u",
        str(os.getuid()),
        "-o",
        "pid=,ppid=,stat=,pcpu=,pmem=,etime=,comm=,args=",
        "--sort=-pcpu",
    ]
    output = subprocess.run(
        command, check=True, capture_output=True, text=True
    ).stdout
    rows: list[dict[str, object]] = []
    for line in output.splitlines():
        parts = line.strip().split(None, 7)
        if len(parts) != 8:
            continue
        pid, ppid, state, cpu, memory, elapsed, name, full_command = parts
        rows.append(
            {
                "pid": int(pid),
                "ppid": int(ppid),
                "state": state,
                "cpu": cpu,
                "memory": memory,
                "elapsed": elapsed,
                "name": name,
                "command": full_command,
            }
        )
    return rows


def ancestor_pids(pid: int) -> set[int]:
    ancestors = {pid}
    while pid > 1:
        try:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as stat_file:
                # The name in parentheses may contain spaces.
                pid = int(stat_file.read().rsplit(")", 1)[1].split()[1])
        except (FileNotFoundError, IndexError, OSError, ValueError):
            break
        ancestors.add(pid)
    return ancestors


class ProcessSelector(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Cerrar procesos colgados")
        self.geometry("1180x680")
        self.minsize(850, 480)
        self._rows: list[dict[str, object]] = []
        self._protected_pids = ancestor_pids(os.getpid())
        self._kwin_events: queue.Queue[tuple[object, ...]] = queue.Queue()
        self._kwin_windows: dict[str, tuple[int, bool]] = {}
        self._kwin_snapshot_ready = False
        self._kwin_loop = None
        self._qdbus = shutil.which("qdbus6") or shutil.which("qdbus")
        self._kwin_plugin = f"proton-pilot-process-selector-{os.getpid()}"
        self._kwin_script_path: str | None = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close_app)
        signal.signal(
            signal.SIGTERM, lambda _signal, _frame: self.after(0, self._close_app)
        )
        self._start_kwin_monitor()
        self.refresh(select_gamescope=True)
        self.after(200, self._poll_kwin_events)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        ttk.Label(
            outer,
            text=(
                "Selecciona uno o varios procesos. Se cerrarán también sus "
                "procesos hijo."
            ),
            font=("", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            outer,
            text=(
                "Prueba primero «Terminar normalmente». Usa «Forzar cierre» "
                "solo si el proceso no responde."
            ),
        ).pack(anchor="w", pady=(3, 10))
        ttk.Label(
            outer,
            text=(
                "En rojo: proceso bloqueado por Linux o ventana que KWin marca "
                "como «no responde»."
            ),
            foreground="#d32f2f",
        ).pack(anchor="w", pady=(0, 10))

        search_row = ttk.Frame(outer)
        search_row.pack(fill="x", pady=(0, 8))
        ttk.Label(search_row, text="Buscar:").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=7)
        search_entry.bind("<KeyRelease>", lambda _event: self._populate())
        ttk.Button(
            search_row, text="Limpiar", command=lambda: self.search_var.set("")
        ).pack(side="left")
        ttk.Button(search_row, text="Actualizar", command=self.refresh).pack(
            side="left", padx=(7, 0)
        )

        columns = ("pid", "state", "cpu", "memory", "elapsed", "name", "command")
        table_frame = ttk.Frame(outer)
        table_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended"
        )
        headings = {
            "pid": "PID",
            "state": "Estado",
            "cpu": "CPU %",
            "memory": "RAM %",
            "elapsed": "Tiempo",
            "name": "Proceso",
            "command": "Comando",
        }
        widths = {
            "pid": 75,
            "state": 150,
            "cpu": 75,
            "memory": 75,
            "elapsed": 90,
            "name": 165,
            "command": 560,
        }
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=55,
                stretch=column == "command",
            )
        vertical = ttk.Scrollbar(
            table_frame, orient="vertical", command=self.tree.yview
        )
        horizontal = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(
            yscrollcommand=vertical.set, xscrollcommand=horizontal.set
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.tree.tag_configure("protected", foreground="#777777")
        self.tree.tag_configure(
            "hung", foreground="#ffffff", background="#b71c1c"
        )
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._update_status())

        bottom = ttk.Frame(outer)
        bottom.pack(fill="x", pady=(10, 0))
        self.status_var = tk.StringVar(value="Ningún proceso seleccionado")
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left")
        ttk.Button(bottom, text="Cerrar ventana", command=self._close_app).pack(
            side="right"
        )
        ttk.Button(
            bottom,
            text="Forzar cierre",
            command=lambda: self.terminate_selected(signal.SIGKILL),
        ).pack(side="right", padx=7)
        ttk.Button(
            bottom,
            text="Terminar normalmente",
            command=lambda: self.terminate_selected(signal.SIGTERM),
        ).pack(side="right")

    def refresh(self, select_gamescope: bool = False) -> None:
        selected = set(self.tree.selection())
        try:
            self._rows = process_rows()
        except (OSError, subprocess.SubprocessError) as error:
            messagebox.showerror(
                "No se pudo leer la lista de procesos", str(error), parent=self
            )
            return
        self._populate()
        visible = set(self.tree.get_children())
        still_selected = selected & visible
        if still_selected:
            self.tree.selection_set(tuple(still_selected))
        elif select_gamescope:
            gamescope = next(
                (
                    str(row["pid"])
                    for row in self._rows
                    if "gamescope" in str(row["name"]).lower()
                ),
                None,
            )
            if gamescope and gamescope in visible:
                self.tree.selection_set(gamescope)
                self.tree.focus(gamescope)
                self.tree.see(gamescope)
        self._update_status()

    def _populate(self) -> None:
        query = self.search_var.get().strip().lower()
        selected = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        kwin_window_pids = {
            window_pid for window_pid, _state in self._kwin_windows.values()
        }
        unresponsive_pids = {
            window_pid
            for window_pid, unresponsive in self._kwin_windows.values()
            if unresponsive
        }
        for row in self._rows:
            haystack = f"{row['pid']} {row['name']} {row['command']}".lower()
            if query and query not in haystack:
                continue
            pid = int(row["pid"])
            protected = (
                pid in self._protected_pids or str(row["name"]) in PROTECTED_NAMES
            )
            process_name = str(row["name"]).lower()
            kwin_unresponsive = pid in unresponsive_pids
            stale_gamescope = (
                self._kwin_snapshot_ready
                and process_name in {"gamescope", "gamescope-wl"}
                and pid not in kwin_window_pids
            )
            problem = (
                str(row["state"])[:1] in PROBLEM_STATES
                or kwin_unresponsive
                or stale_gamescope
            )
            display_state = str(row["state"])
            if kwin_unresponsive:
                display_state += " · NO RESPONDE"
            elif stale_gamescope:
                display_state += " · SIN VENTANA"
            tags = []
            if protected:
                tags.append("protected")
            if problem:
                tags.append("hung")
            self.tree.insert(
                "",
                "end",
                iid=str(pid),
                values=(
                    pid,
                    display_state,
                    row["cpu"],
                    row["memory"],
                    row["elapsed"],
                    row["name"],
                    row["command"],
                ),
                tags=tuple(tags),
            )
        visible = set(self.tree.get_children())
        self.tree.selection_set(tuple(selected & visible))
        self._update_status()

    def _start_kwin_monitor(self) -> None:
        """Receive KWin's unresponsive-window state when it is available."""
        if not self._qdbus:
            return
        service = f"org.drbermejor.ProtonPilot.ProcessSelector.p{os.getpid()}"
        script = f"""
"use strict";
function windowId(window) {{
    return String(window.internalId);
}}
function report(window) {{
    callDBus(
        "{service}",
        "/Selector",
        "org.drbermejor.ProtonPilot.ProcessSelector",
        "Report",
        windowId(window),
        window.pid,
        window.unresponsive
    );
}}
function watch(window) {{
    report(window);
    window.unresponsiveChanged.connect(function () {{ report(window); }});
}}
workspace.windowList().forEach(watch);
workspace.windowAdded.connect(watch);
workspace.windowRemoved.connect(function (window) {{
    callDBus(
        "{service}",
        "/Selector",
        "org.drbermejor.ProtonPilot.ProcessSelector",
        "Remove",
        windowId(window)
    );
}});
callDBus(
    "{service}",
    "/Selector",
    "org.drbermejor.ProtonPilot.ProcessSelector",
    "SnapshotDone"
);
"""
        try:
            runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
            temporary = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix="proton-pilot-process-selector-",
                suffix=".js",
                dir=runtime_dir,
                delete=False,
            )
            with temporary:
                temporary.write(script)
            self._kwin_script_path = temporary.name
        except OSError:
            return
        threading.Thread(target=self._kwin_monitor_worker, daemon=True).start()

    def _kwin_monitor_worker(self) -> None:
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib

            event_queue = self._kwin_events

            class Listener(dbus.service.Object):
                @dbus.service.method(
                    "org.drbermejor.ProtonPilot.ProcessSelector",
                    in_signature="sib",
                )
                def Report(self, window_id, pid, unresponsive):
                    event_queue.put(
                        ("report", str(window_id), int(pid), bool(unresponsive))
                    )

                @dbus.service.method(
                    "org.drbermejor.ProtonPilot.ProcessSelector",
                    in_signature="s",
                )
                def Remove(self, window_id):
                    event_queue.put(("remove", str(window_id)))

                @dbus.service.method(
                    "org.drbermejor.ProtonPilot.ProcessSelector"
                )
                def SnapshotDone(self):
                    event_queue.put(("snapshot",))

            DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            service = (
                f"org.drbermejor.ProtonPilot.ProcessSelector.p{os.getpid()}"
            )
            bus_name = dbus.service.BusName(service, bus)
            listener = Listener(bus, "/Selector")
            load_result = subprocess.run(
                [
                    str(self._qdbus),
                    "org.kde.KWin",
                    "/Scripting",
                    "org.kde.kwin.Scripting.loadScript",
                    str(self._kwin_script_path),
                    self._kwin_plugin,
                ],
                capture_output=True,
                text=True,
            )
            if load_result.returncode != 0:
                return
            subprocess.run(
                [
                    str(self._qdbus),
                    "org.kde.KWin",
                    "/Scripting",
                    "org.kde.kwin.Scripting.start",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            loop = GLib.MainLoop()
            self._kwin_loop = loop
            # Keep the D-Bus service alive while the GLib loop is running.
            _keep_alive = (bus_name, listener)
            loop.run()
        except (ImportError, OSError):
            pass
        finally:
            if self._qdbus:
                subprocess.run(
                    [
                        self._qdbus,
                        "org.kde.KWin",
                        "/Scripting",
                        "org.kde.kwin.Scripting.unloadScript",
                        self._kwin_plugin,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            if self._kwin_script_path:
                try:
                    os.unlink(self._kwin_script_path)
                except OSError:
                    pass

    def _poll_kwin_events(self) -> None:
        changed = False
        while True:
            try:
                event = self._kwin_events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "report":
                self._kwin_windows[str(event[1])] = (
                    int(event[2]),
                    bool(event[3]),
                )
                changed = True
            elif event[0] == "remove":
                self._kwin_windows.pop(str(event[1]), None)
                changed = True
            elif event[0] == "snapshot":
                self._kwin_snapshot_ready = True
                changed = True
        if changed:
            self._populate()
        self.after(200, self._poll_kwin_events)

    def _close_app(self) -> None:
        if self._kwin_loop is not None:
            self._kwin_loop.quit()
        self.destroy()

    def _update_status(self) -> None:
        count = len(self.tree.selection())
        problem_count = sum(
            1
            for item in self.tree.get_children()
            if "hung" in self.tree.item(item, "tags")
        )
        problem_text = (
            f" · {problem_count} en estado problemático" if problem_count else ""
        )
        if count == 0:
            self.status_var.set(
                f"{len(self.tree.get_children())} procesos"
                f"{problem_text} · ninguno seleccionado"
            )
        else:
            self.status_var.set(
                f"{len(self.tree.get_children())} procesos"
                f"{problem_text} · {count} seleccionado(s)"
            )

    def _descendants(self, roots: set[int]) -> set[int]:
        children: dict[int, set[int]] = {}
        for row in process_rows():
            children.setdefault(int(row["ppid"]), set()).add(int(row["pid"]))
        result = set(roots)
        pending = list(roots)
        while pending:
            parent = pending.pop()
            for child in children.get(parent, set()):
                if child not in result:
                    result.add(child)
                    pending.append(child)
        return result

    def terminate_selected(self, requested_signal: signal.Signals) -> None:
        selected = {int(pid) for pid in self.tree.selection()}
        if not selected:
            messagebox.showinfo(
                "Selecciona un proceso",
                "Selecciona al menos un proceso de la lista.",
                parent=self,
            )
            return

        rows_by_pid = {int(row["pid"]): row for row in self._rows}
        protected = {
            pid
            for pid in selected
            if pid in self._protected_pids
            or str(rows_by_pid.get(pid, {}).get("name", "")) in PROTECTED_NAMES
        }
        if protected:
            names = ", ".join(
                f"{rows_by_pid[pid]['name']} ({pid})"
                for pid in sorted(protected)
                if pid in rows_by_pid
            )
            messagebox.showwarning(
                "Proceso protegido",
                (
                    "Por seguridad, este selector no cierra componentes "
                    f"esenciales del escritorio ni a sí mismo:\n\n{names}"
                ),
                parent=self,
            )
            return

        descriptions = "\n".join(
            f"• {rows_by_pid[pid]['name']} (PID {pid})"
            for pid in sorted(selected)
            if pid in rows_by_pid
        )
        force = requested_signal == signal.SIGKILL
        action = "FORZAR el cierre" if force else "terminar normalmente"
        detail = (
            "\n\nEl cierre forzado puede causar pérdida de datos."
            if force
            else (
                "\n\nSi no desaparece, vuelve a abrir el selector y usa "
                "«Forzar cierre»."
            )
        )
        if not messagebox.askyesno(
            "Confirmar cierre",
            f"¿Quieres {action} de estos procesos y sus procesos hijo?\n\n"
            f"{descriptions}{detail}",
            icon="warning" if force else "question",
            parent=self,
        ):
            return

        try:
            targets = self._descendants(selected)
        except (OSError, subprocess.SubprocessError):
            targets = selected
        targets -= self._protected_pids

        succeeded = 0
        errors: list[str] = []
        # Signal children first so that the selected parent cannot orphan them.
        for pid in sorted(targets, reverse=True):
            try:
                os.kill(pid, requested_signal)
                succeeded += 1
            except ProcessLookupError:
                pass
            except PermissionError:
                errors.append(str(pid))

        if errors:
            messagebox.showwarning(
                "Cierre parcial",
                (
                    f"Se envió la señal a {succeeded} proceso(s), pero faltaron "
                    f"permisos para los PID: {', '.join(errors)}"
                ),
                parent=self,
            )
        self.after(800, self.refresh)


if __name__ == "__main__":
    app = ProcessSelector()
    app.mainloop()
