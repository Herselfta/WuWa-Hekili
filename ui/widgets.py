import os
from PySide6.QtWidgets import (QWidget, QLabel, QFrame, QHBoxLayout,
                               QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, Signal, QRect
from utils.config_manager import config

# ============================================================
# 组件 1: ActionWidget (用于游戏内的透明悬浮窗)
# ============================================================
class ActionWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        # 为透明度动画做准备
        self.op_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.op_effect)
        self.op_effect.setOpacity(1.0)

        self.default_border = "#808080"
        self.heavy_border = "#FF4500"
        self.current_border = "#FFD700"
        self.current_variant = None

        # 单一的主文字标签
        self.text_label = QLabel(self)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 角色标识标签 (1, 2, 3)
        self.char_label = QLabel(self)
        self.char_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.char_label.setStyleSheet("""
            background-color: rgba(0, 150, 255, 200); 
            color: white; 
            font-weight: bold; 
            font-size: 12px;
            border-radius: 4px;
        """)

        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            background-color: rgba(255, 0, 0, 180); 
            color: white; 
            font-weight: bold; 
            font-size: 10px;
            border-radius: 2px;
        """)
        self.status_label.hide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        
        # 文字标签覆盖全屏居中
        self.text_label.setGeometry(self.rect())
        
        # 动态调整字体大小 (大约为高度的40%)
        font_size = max(10, int(h * 0.4))
        self.text_label.setStyleSheet(f"""
            color: #00FF00; 
            font-family: 'Segoe UI', 'Microsoft YaHei';
            font-weight: bold;
            font-size: {font_size}px;
            background: transparent;
        """)
        
        # 角色标签放在左上角
        char_size = max(14, int(h * 0.25))
        self.char_label.setGeometry(2, 2, char_size, char_size)
        self.char_label.setStyleSheet(f"""
            background-color: rgba(0, 150, 255, 200); 
            color: white; 
            font-weight: bold; 
            font-size: {max(9, int(char_size * 0.7))}px;
            border-radius: 4px;
        """)
        
        # 状态标签（如 HOLD）放在底部
        self.status_label.setGeometry(2, h - int(h * 0.25) - 2, w - 4, int(h * 0.25))

    def update_style(self, variant=None, is_current=False):
        self.current_variant = variant
        border_color = self.current_border if is_current else self.default_border
        if variant and "heavy" in variant.lower():
            border_color = self.heavy_border

        border_width = 3 if is_current else 1
        self.setStyleSheet(f"""
            ActionWidget {{
                background-color: rgba(0, 0, 0, 180);
                border: {border_width}px solid {border_color};
                border-radius: 12px;
            }}
        """)

    def set_data(self, data):
        variant = data.get("variant")
        desc = data.get("desc", "")
        action_type = data.get("type", "")

        # 从配置中反查按键名称
        device = config.get("settings.current_device", "keyboard")
        lookup_key = action_type
        if action_type == "intro" and data.get("next_char"):
            lookup_key = f"intro_{data.get('next_char')}"
        elif action_type == "none":
            lookup_key = "none" # 处理启动状态
        
        btn_name = config.get(f"keymaps.{device}.{lookup_key}", "")
        if action_type == "none":
            display_text = "..."
        elif not btn_name:
            if action_type == "intro" and data.get("next_char"):
                display_text = str(data.get("next_char"))
            else:
                display_text = desc[:1] if desc else "?"
        else:
            # 简化名称：keyboard_e -> E, mouse_left -> 左键
            raw_suffix = btn_name.split("_")[-1].lower()
            if "left" in raw_suffix: display_text = "左键"
            elif "right" in raw_suffix: display_text = "右键"
            elif "space" in raw_suffix: display_text = "空格"
            elif "scroll" in raw_suffix: display_text = "中键"
            else: display_text = raw_suffix.upper()
        
        self.text_label.setText(display_text)

        # 角色标识显示
        char_name = data.get("char_name", "")
        if char_name:
            self.char_label.setText(str(char_name))
            self.char_label.show()
        else:
            self.char_label.hide()

        # 3. 处理变体文本 (如 HOLD)
        if variant:
            v_lower = variant.lower()
            if "heavy" in v_lower:
                self.status_label.setText("HOLD"); self.status_label.show()
            elif "forte" in v_lower:
                self.status_label.setText("FORTE"); self.status_label.show()
            else:
                self.status_label.hide()
        else:
            self.status_label.hide()


# ============================================================
# 组件 2: ActionEditorRow (用于流程编辑器的每一行)
# ============================================================
class ActionEditorRow(QWidget):
    def __init__(self, index, action_data, char_name, parent=None):
        super().__init__(parent)
        self.index = index
        self.action_data = action_data
        self.char_name = char_name

        self.setStyleSheet("background-color: white; border-bottom: 1px solid #eee;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.lbl_idx = QLabel(f"<b>{index + 1:02d}</b>")
        self.lbl_idx.setFixedWidth(30)
        layout.addWidget(self.lbl_idx)

        # 类型标签 (例如 [技能], [普攻])
        type_lbl = QLabel(f"[{action_data.get('type', 'ACT')}]")
        type_lbl.setFixedWidth(80)
        type_lbl.setStyleSheet("color: #666; font-weight: bold;")
        layout.addWidget(type_lbl)

        # 描述文本
        desc_text = f"{action_data.get('desc', '')} (角色: {char_name})"
        self.lbl_desc = QLabel(desc_text)
        layout.addWidget(self.lbl_desc)
        
        layout.addStretch()