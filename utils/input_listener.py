import keyboard
import ctypes
import time
from PySide6.QtCore import QThread, Signal
from utils.config_manager import config
from utils.logger import log


class InputListener(QThread):
    action_detected = Signal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

        self.key_to_action = {}
        self.mouse_to_action = {}
        self.mouse_states = {"left": False, "right": False, "middle": False}

        self._build_lookup_table()

    def _build_lookup_table(self):
        log.info("🔍 --- 正在构建键盘/鼠标映射表 ---")
        action_map_kb = config.get("keymaps.keyboard", {})
        for action, filename in action_map_kb.items():
            if not filename: continue

            if filename.startswith("key_") or filename.startswith("keyboard_"):
                # "keyboard_f" -> "f", "key_space" -> "space"
                real_key = filename.replace("key_", "").replace("keyboard_", "").split("_")[0]
                self.key_to_action[real_key.lower()] = action

            elif filename.startswith("mouse_"):
                if "left" in filename:
                    self.mouse_to_action["left"] = action
                elif "right" in filename:
                    self.mouse_to_action["right"] = action
                elif "middle" in filename:
                    self.mouse_to_action["middle"] = action

        log.info(
            f"🎮 监听就绪: 键盘({len(self.key_to_action)}键) | 鼠标({len(self.mouse_to_action)}键)")

    def reload_mapping(self):
        log.info("🔄[Listener] 正在重载按键映射...")
        self.key_to_action.clear()
        self.mouse_to_action.clear()
        self._build_lookup_table()

    def _on_keyboard_event(self, event):
        if not self.running: return
        action = self.key_to_action.get(event.name.lower())
        if action:
            if event.event_type == "down":
                self.action_detected.emit(action, True)
            elif event.event_type == "up":
                self.action_detected.emit(action, False)

    def run(self):
        keyboard.hook(self._on_keyboard_event)
        log.info("🎮 [Listener] 全局监听已启动...")

        mouse_vk_codes = {"left": 0x01, "right": 0x02, "middle": 0x04}

        while self.running:
            # === 1. 鼠标底层轮询 ===
            for btn_name, vk_code in mouse_vk_codes.items():
                action = self.mouse_to_action.get(btn_name)
                state = ctypes.windll.user32.GetAsyncKeyState(vk_code)
                is_pressed = (state & 0x8000) != 0
                was_pressed = self.mouse_states[btn_name]

                if is_pressed and not was_pressed:
                    self.mouse_states[btn_name] = True
                    if action:
                        self.action_detected.emit(action, True)
                elif not is_pressed and was_pressed:
                    self.mouse_states[btn_name] = False
                    if action:
                        self.action_detected.emit(action, False)

            self.msleep(5)

    def stop(self):
        self.running = False
        keyboard.unhook_all()
        self.wait()