import os
import json
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QLineEdit, QTextEdit, QPushButton, QComboBox,
                               QStackedWidget, QFormLayout, QGroupBox, QMessageBox, QProgressBar, QInputDialog,
                               QScrollArea)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap

from tools.generic_parser import GenericScriptParser
from utils.logger import log


class RoutineUploaderWindow(QWidget):
    routine_saved = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("连招流程编辑器")
        self.resize(700, 800)

        self.layout = QVBoxLayout(self)
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        # 状态
        self.is_edit_mode = False
        self.current_editing_filename = ""
        self.parsed_opener = []
        self.parsed_loop = []
        self.temp_team_mapping = {}

        self.init_input_page()
        self.init_preview_page()

    def init_input_page(self):
        self.input_page = QWidget()
        layout = QVBoxLayout(self.input_page)

        char_group = QGroupBox("1. 队伍配置 (输入代称，如: 忌, 莫, 散)")
        char_layout = QFormLayout(char_group)
        self.char_inputs = []
        for i in range(3):
            alias = QLineEdit()
            alias.setPlaceholderText(f"{i + 1} 号位代称 (可输入多个，用逗号分隔)")
            self.char_inputs.append(alias)
            char_layout.addRow(f"{i + 1} 号位:", alias)
        layout.addWidget(char_group)

        text_group = QGroupBox("2. 连招脚本 (黑话/简写)")
        text_layout = QVBoxLayout(text_group)
        text_layout.addWidget(QLabel("启动轴 (Opener):"))
        self.opener_edit = QTextEdit()
        self.opener_edit.setPlaceholderText("例如: 爱aaaa莫aa...")
        text_layout.addWidget(self.opener_edit)

        text_layout.addWidget(QLabel("循环轴 (Loop):"))
        self.loop_edit = QTextEdit()
        self.loop_edit.setPlaceholderText("例如: 莫raaa...")
        text_layout.addWidget(self.loop_edit)
        layout.addWidget(text_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.btn_parse = QPushButton("✨ 解析并预览连招")
        self.btn_parse.setMinimumHeight(45)
        self.btn_parse.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; border-radius: 5px;")
        self.btn_parse.clicked.connect(self.start_parsing_animation)
        layout.addWidget(self.btn_parse)

        self.stacked_widget.addWidget(self.input_page)

    def init_preview_page(self):
        self.preview_page = QWidget()
        layout = QVBoxLayout(self.preview_page)

        layout.addWidget(QLabel("<h2>解析结果详情校验</h2>", alignment=Qt.AlignmentFlag.AlignCenter))

        # 可滚动的区域显示图标列表
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroll_content = QWidget()
        self.scroll_list_layout = QVBoxLayout(self.scroll_content)
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area)

        btn_layout = QHBoxLayout()
        self.btn_back = QPushButton("⬅️ 返回修改文本")
        self.btn_back.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))

        self.btn_save = QPushButton("💾 确认并保存流程")
        self.btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; height: 35px;")
        self.btn_save.clicked.connect(self.save_routine)

        btn_layout.addWidget(self.btn_back)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        self.stacked_widget.addWidget(self.preview_page)

    def load_existing_routine(self, json_path):
        """编辑模式：回填数据"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.is_edit_mode = True
            self.current_editing_filename = os.path.basename(json_path)

            team_aliases = data.get("team_aliases", {})
            for i in range(3):
                self.char_inputs[i].setText(team_aliases.get(str(i + 1), ""))

            self.opener_edit.setPlainText(data.get("original_opener", ""))
            self.loop_edit.setPlainText(data.get("original_loop", ""))
            self.stacked_widget.setCurrentIndex(0)
            self.btn_save.setText("💾 覆盖修改并保存")
            self.show()
        except Exception as e:
            log.error(f"加载流程失败: {e}")

    def start_parsing_animation(self):
        """播放进度条动画"""
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.btn_parse.setEnabled(False)

        # 准备映射数据
        self.temp_team_mapping = {}
        for i, alias_input in enumerate(self.char_inputs):
            alias_text = alias_input.text().strip()
            if not alias_text:
                continue
            
            # 使用第一个代称作为主要显示名称
            aliases = [x.strip() for x in alias_text.replace("，", ",").split(",") if x.strip()]
            if not aliases:
                continue
            
            main_name = aliases[0]
            self.temp_team_mapping[main_name] = (i + 1, main_name, aliases)

        self.timer = QTimer()
        self.timer.timeout.connect(self._update_anim)
        self.anim_val = 0
        self.timer.start(5)

    def _update_anim(self):
        self.anim_val += 5
        self.progress_bar.setValue(self.anim_val)
        if self.anim_val >= 100:
            self.timer.stop()
            self.progress_bar.hide()
            self.btn_parse.setEnabled(True)
            self._execute_parse()

    def _execute_parse(self):
        """执行解析并渲染可视化列表"""
        try:
            parser = GenericScriptParser(self.temp_team_mapping)
            self.parsed_opener = parser.parse(self.opener_edit.toPlainText())
            self.parsed_loop = parser.parse(self.loop_edit.toPlainText())

            self.render_all_previews()
            self.stacked_widget.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.critical(self, "解析失败", str(e))

    def render_all_previews(self):
        """渲染带图标的可视化预览行"""

        # 1. 💡 暴力清空布局 (防止重复显示)
        # 这种 reversed 迭代并 setParent(None) 是 Qt 最稳妥的清空方式
        for i in reversed(range(self.scroll_list_layout.count())):
            item = self.scroll_list_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                # 如果里面有子布局也要处理，但这里我们主要是层叠 Widget
                pass
            else:
                self.scroll_list_layout.removeItem(item)

        # 2. 不再使用资源管理器
        self.opener_widgets = []
        self.loop_widgets = []

        # 3. 内部填充函数
        def fill_section(script, widget_list, title):
            # 添加分区标题
            header = QLabel(f"<h3 style='color: #FFA500;'>{title} ({len(script)} 步)</h3>")
            self.scroll_list_layout.addWidget(header)

            # 模拟状态
            current_char_id = 1
            team_dict = {str(cid): name for name, (cid, name, al) in self.temp_team_mapping.items()}

            from ui.widgets import ActionEditorRow  # 局部导入防止循环引用

            for i, act in enumerate(script):
                char_name = team_dict.get(str(current_char_id), "Unknown")

                # 如果是切人，先更新指针再取名字
                if act["type"] == "intro":
                    current_char_id = act.get("next_char", current_char_id)
                    char_name = team_dict.get(str(current_char_id), "Unknown")

                # 创建编辑器组件
                row = ActionEditorRow(i, act, char_name)
                self.scroll_list_layout.addWidget(row)
                widget_list.append(row)

        # 4. 执行渲染
        if self.parsed_opener:
            fill_section(self.parsed_opener, self.opener_widgets, "🌟 启动轴预览")

        # 加个分割空隙
        self.scroll_list_layout.addSpacing(40)

        if self.parsed_loop:
            fill_section(self.parsed_loop, self.loop_widgets, "🔁 循环轴预览")

        self.scroll_list_layout.addStretch()  # 把内容顶到最上面


    def save_routine(self):
        """保存逻辑"""
        default = self.current_editing_filename.replace(".json", "") if self.is_edit_mode else ""
        name, ok = QInputDialog.getText(self, "保存流程", "起个名字:", QLineEdit.EchoMode.Normal, default)
        if not (ok and name): return

        def update_script_with_choices(original_script):
            new_script = []
            for i, act in enumerate(original_script):
                final_act = dict(act)

                # 变体只管逻辑，不管图片了
                if "heavy" in final_act.get("variant", "").lower() or final_act.get("desc", "").startswith("重击"):
                    final_act["variant"] = "heavy"
                elif "forte" in final_act.get("variant", "").lower() or final_act.get("desc", "").startswith("核心"):
                    final_act["variant"] = "forte"
                new_script.append(final_act)
            return new_script

        final_opener = update_script_with_choices(self.parsed_opener)
        final_loop = update_script_with_choices(self.parsed_loop)

        save_data = {
            "name": name,
            "team_config": {str(cid): name for name, (cid, name, al) in self.temp_team_mapping.items()},
            "team_aliases": {str(cid): ",".join(al) for name, (cid, name, al) in self.temp_team_mapping.items()},
            "original_opener": self.opener_edit.toPlainText(),
            "original_loop": self.loop_edit.toPlainText(),
            "opener_script": final_opener,
            "loop_script": final_loop,
            "initial_char_index": 1
        }

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        routines_dir = os.path.join(base_dir, "configs", "routines")
        os.makedirs(routines_dir, exist_ok=True)

        file_path = os.path.join(routines_dir, f"{name}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=4)

        QMessageBox.information(self, "完成", "流程已保存。")
        self.routine_saved.emit(file_path)
        self.close()