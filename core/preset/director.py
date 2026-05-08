import time
from utils.config_manager import config
from utils.logger import log


class Director:
    def __init__(self, team_config, opener_script, loop_script, start_char_index):
        self.team = team_config
        self.opener = opener_script
        self.loop = loop_script

        self.is_in_opener = True if self.opener else False
        self.step_index = 0
        self.current_char_idx = start_char_index
        
        # 💡 安全检查：如果初始角色不在队伍配置里，尝试自动修正
        if self.current_char_idx not in self.team and self.team:
            fallback_idx = list(self.team.keys())[0]
            log.warning(f"⚠️ 初始角色索引 {self.current_char_idx} 不在队伍配置中，已自动修正为 {fallback_idx} ({self.team[fallback_idx]})")
            self.current_char_idx = fallback_idx
        elif not self.team:
            log.error("❌ 队伍配置为空！请检查 JSON 剧本中的 team_config 字段。")

        # 状态机变量
        self.is_holding = False
        self.expected_release_action = None

        # 💡 核心修复：历史状态栈 (用于完美回退)
        # 存储格式: (step_index, is_in_opener, current_char_idx)
        self.history_stack = []

    def get_current_script(self):
        return self.opener if self.is_in_opener else self.loop

    def get_visual_data(self, preview_count=3):
        """获取[历史, 当前, 预告1, 预告2]"""
        result = []
        current_script = self.get_current_script()
        if not current_script: return []

        # 1. 处理历史记录预览 (对应 index -1)
        if not self.history_stack:
            result.append({"type": "none", "desc": "START", "is_history": True, "char_name": ""})
        else:
            # 从栈顶取上一个真实的状态
            h_idx, h_opener, h_char = self.history_stack[-1]
            prev_action = (self.opener if h_opener else self.loop)[h_idx]
            
            # 处理历史记录预览中的角色名：如果是切人，显示切后的角色；否则显示当时角色
            display_char = prev_action.get("next_char") if prev_action["type"] == "intro" else h_char
            result.append({
                "type": prev_action["type"],
                "next_char": prev_action.get("next_char"),
                "desc": prev_action.get("desc", ""),
                "is_current": False,
                "is_history": True,
                "char_name": self.team.get(display_char, str(display_char))
            })

        # 2. 处理当前和未来预览
        # 💡 核心修复：真实模拟剧本推进（包括从 opener 过渡到 loop），而不是简单取余
        sim_idx = self.step_index
        sim_opener = self.is_in_opener
        sim_char = self.current_char_idx

        for i in range(preview_count):
            active_script = self.opener if sim_opener else self.loop
            if not active_script:
                break
            
            # 安全保护
            if sim_idx >= len(active_script):
                sim_idx = 0

            action = active_script[sim_idx]

            # 💡 关键：预测未来的角色变化
            display_char_idx = sim_char
            if action["type"] == "intro":
                next_c = action.get("next_char")
                if next_c:
                    display_char_idx = next_c
                    sim_char = next_c  # 更新后续步骤的预测基准

            result.append({
                "type": action["type"],
                "next_char": action.get("next_char"),
                "desc": action.get("desc", ""),
                "variant": action.get("variant"),
                "char_name": self.team.get(display_char_idx, str(display_char_idx)),
                "is_current": (i == 0),
                "is_history": False
            })

            # 模拟推进 (逻辑与 advance 完全一致)
            sim_idx += 1
            if sim_opener and sim_idx >= len(self.opener):
                sim_opener = False  # 启动轴结束，进入循环轴
                sim_idx = 0
            elif not sim_opener and sim_idx >= len(self.loop):
                sim_idx = 0  # 循环轴结束，从头开始循环
        return result

    def input_received(self, input_action, is_down):
        current_script = self.get_current_script()
        if not current_script or self.step_index >= len(current_script): return False

        expected_action = current_script[self.step_index]
        expected_type = expected_action.get("type")

        # 匹配检查
        is_match = False
        if expected_type == "intro":
            if input_action == f"intro_{expected_action.get('next_char')}": is_match = True
        elif input_action == expected_type or (expected_type == "heavy" and input_action == "basic"):
            is_match = True

        # 💡 逻辑分流：哪些动作需要“松开触发”，哪些“按下即触发”？
        # 只有 普攻(basic)、技能(skill)、大招(ult) 建议用松开触发来处理合轴
        # 切人(intro)、闪避(dodge)、跳跃(jump) 必须按下即触发，否则卡手
        is_instant = expected_type in ["intro", "dodge", "jump"]

        if is_down:
            if is_match:
                if is_instant:
                    log.info(f"⚡ 瞬发动作匹配: {input_action}")
                    self.advance()
                    return True
                else:
                    if not self.is_holding:
                        self.is_holding = True
                        self.expected_release_action = input_action
                        log.debug(f"⏳ 缓冲动作确认: {input_action}，等待松开...")
            return False
        else:
            # 松开逻辑
            if self.is_holding and input_action == self.expected_release_action:
                self.is_holding = False
                log.info(f"➡️ 缓冲动作完成: {input_action}")
                self.advance()
                return True
            return False

    def advance(self):
        """推进时保存历史"""
        current_script = self.get_current_script()

        # 1. 存入历史栈 (存入的是当前还没变之前的状态)
        self.history_stack.append((self.step_index, self.is_in_opener, self.current_char_idx))
        if len(self.history_stack) > 20: self.history_stack.pop(0)  # 最多记20步

        # 2. 执行逻辑变更
        current_action = current_script[self.step_index]
        if current_action.get("type") == "intro":
            next_char = current_action.get("next_char")
            if next_char:
                if next_char in self.team:
                    self.current_char_idx = next_char
                else:
                    log.warning(f"⚠️ 剧本尝试切换到角色索引 {next_char}，但该索引未在 team_config 中定义！")
                    self.current_char_idx = next_char # 仍然赋值，但上面已经警告了

        self.step_index += 1
        if self.is_in_opener and self.step_index >= len(self.opener):
            self.is_in_opener = False
            self.step_index = 0
        elif not self.is_in_opener and self.step_index >= len(self.loop):
            self.step_index = 0

    def rollback(self):
        """从历史栈恢复状态"""
        if not self.history_stack:
            log.warning("⚠️ 已经回退到头了，无法再回退")
            return False

        self.is_holding = False
        # 弹出最后一次保存的状态
        prev_step, prev_opener, prev_char = self.history_stack.pop()

        self.step_index = prev_step
        self.is_in_opener = prev_opener
        self.current_char_idx = prev_char

        log.info(f"⏪ 回退成功：回到角色 {self.team.get(self.current_char_idx)}，步骤 {self.step_index}")
        return True

    def reset(self):
        self.step_index = 0
        self.is_in_opener = True if self.opener else False
        self.is_holding = False
        self.history_stack.clear()