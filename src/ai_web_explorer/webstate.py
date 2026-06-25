import dataclasses
import json
import typing
import uuid
from openai.types.chat import ChatCompletionMessageToolCall
import numpy as np

ActionStatus = typing.Literal["none", "success", "failure"]
# status的三种状态，其中none表示还未执行

# 动作（待探索边）定义
@dataclasses.dataclass
class Action:
    description: str
    part: int   # 这个动作对应 HTML 的第几块（0, 1, 2...）
    priority: int    # 选择优先级高的动作先执行
    status: ActionStatus = dataclasses.field(default="none")
    function_calls: list[dict] = dataclasses.field(default_factory=list)    # AI 生成的 Playwright 操作序列

    def dict(self, simple=False):

        if simple:
            return self.description

        return {
            "description": self.description,
            "part": self.part,
            "priority": self.priority,
            "status": self.status,
            "function_calls": [f.model_dump() for f in self.function_calls],
        }

    @staticmethod
    def from_dict(action_raw) -> "Action":
        return Action(
            description=action_raw["description"],
            part=action_raw["part"],
            priority=action_raw["priority"],
            status=action_raw["status"],
            function_calls=[ChatCompletionMessageToolCall(**f) for f in action_raw["function_calls"]],  # type: ignore
        )

# 已探索边
@dataclasses.dataclass
class StateTransition:
    action: Action
    state_new: "WebState"

    def dict(self, simple=False):
        return {
            "action": self.action.dict(simple),
            "state_new": str(self.state_new.ws_id),
        }

# 网页状态（节点）定义
@dataclasses.dataclass
class WebState:
    title: str
    title_embedding: list[float]
    urls: list[str]     # 到达这个状态的所有 URL（去重后合并）
    description: list[dict]     # AI对页面各分块的结构化描述
    actions: list[Action]
    transitions: list[StateTransition]      # 从这个页面出发的已执行跳转
    ws_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)    # 全局唯一标识

    # 产生随机的候选动作（优先级大于等于11且未执行）
    @property
    def random_action(self) -> None | Action:
        candidates_obvious = [
            action
            for action in self.actions
            if action.status == "none" and action.priority >= 11
        ]
        # 取优先级大于等于11的动作作为明显候选动作
        if candidates_obvious:
            candidates_obvious = sorted(
                candidates_obvious, key=lambda x: x.priority, reverse=True
            )
            return candidates_obvious[0]
        candidates = [action for action in self.actions if action.status == "none"]
        probabilities = np.array([action.priority for action in candidates])
        probabilities = probabilities / probabilities.sum()

        if candidates:
            return np.random.choice(np.array(candidates), p=probabilities)  # type: ignore

        return None
    
    # 计算相似度用于去重（--优化方向--）
    def cosine_distance(self, embedding: list[float]):
        return np.dot(self.title_embedding, embedding) / (
            np.linalg.norm(self.title_embedding) * np.linalg.norm(embedding)
        )

    def dict(self, simple=False):
        d = {
            "ws_id": str(self.ws_id),
            "title": self.title,
            "urls": self.urls,
            "description": self.description,
            "actions": [a.dict(simple) for a in self.actions],
            "transitions": [t.dict(simple) for t in self.transitions],
        }

        if not simple:
            d["title_embedding"] = self.title_embedding

        return d

# 从文件中加载网页状态
def load_states_from_file(file_path: str) -> list[WebState]:
    with open(file_path, "r") as f:
        json_string = f.read()
        print(json_string)
        webstates_raw = json.loads(json_string)

    webstates = []
    transitions_raw = []

    for ws_raw in webstates_raw:
        ws = WebState(
            title=ws_raw["title"],
            title_embedding=ws_raw["title_embedding"],
            urls=ws_raw["urls"],
            description=ws_raw["description"],
            actions=[Action.from_dict(a) for a in ws_raw["actions"]],
            transitions=[],
            ws_id=uuid.UUID(ws_raw["ws_id"]),
        )
        webstates.append(ws)
        # 从自身（uuid）出发，将所有的 transitions_raw 记录下来，后续再去匹配对应的 WebState 对象
        transitions_raw.extend((uuid.UUID(ws_raw["ws_id"]), t) for t in ws_raw["transitions"] if t)

    for state_id, transition_raw in transitions_raw:
        state_current = next(ws for ws in webstates if ws.ws_id == state_id)
        # next() 函数用于从迭代器中获取下一个元素，这里用于找到当前状态对象
        action = Action.from_dict(transition_raw["action"])
        state_new = next(
            ws for ws in webstates if ws.ws_id == uuid.UUID(transition_raw["state_new"])
        )
        state_current.transitions.append(StateTransition(action, state_new))
        # 这里将当前状态的 transitions 列表中添加一个新的 StateTransition 对象，表示从当前状态通过某个动作到达新的状态
        # state_current是ws类型，即当前节点
    return webstates
