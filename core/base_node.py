#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 基础节点类
提供统一的数据流、消息系统、AI集成接口
"""

import os
import sys
import time
import hashlib
import json
import logging
import traceback
from typing import Dict, Any, List, Optional, Union, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import threading
import queue

try:
    import qlib
    from qlib.workflow import R
    from qlib.utils import init_instance_by_config
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

# 添加 NodeGraphQt 路径
#
# ⚠️ 必须用 append（加到 sys.path **末尾**），不能用 insert(0, ...)。
#    因为 NodeGraphQt 目录下**也有一个 nodes 子包**
#    （RockXFWV21/NodeGraphQt/nodes/）。一旦它排在项目根之前，
#    `import nodes` 会解析到 NodeGraphQt 的那个，把本项目的 nodes 包
#    整个遮蔽掉 —— 表现为 `from nodes.qlib_core_nodes import ...` 报
#    "No module named 'nodes.qlib_core_nodes'"（而节点文件明明存在）。
#    NodeGraphQt 是第三方库，项目自己的包应当优先。
nodegraphqt_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'RockXFWV21', 'NodeGraphQt')
if nodegraphqt_path not in sys.path:
    sys.path.append(nodegraphqt_path)

try:
    from NodeGraphQt import BaseNode
    NODEGRAPHQT_AVAILABLE = True
except ImportError:
    NODEGRAPHQT_AVAILABLE = False
    # 创建占位符
    class BaseNode:
        pass

logger = logging.getLogger(__name__)

class RockXQlibNodeStatus(Enum):
    """节点状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"
    PAUSED = "paused"

class RockXQlibPortType(Enum):
    """端口类型枚举"""
    INPUT = "input"
    OUTPUT = "output"

class RockXQlibDataType(Enum):
    """数据类型枚举"""
    ANY = "any"
    DATA_FRAME = "dataframe"
    ARRAY = "array"
    DICT = "dict"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    MODEL = "model"
    STRATEGY = "strategy"
    SIGNAL = "signal"
    # 以下三项供数据类节点使用（历史上的 nodes/data_nodes.py 已删除，
    # 现由 nodes/qlib_data_nodes.py 使用），此前缺失会导致实例化时抛 AttributeError
    HANDLER = "handler"
    DATASET = "dataset"
    PREDICTION = "prediction"

@dataclass
class RockXQlibPortInfo:
    """端口信息"""
    name: str
    port_type: RockXQlibPortType
    data_type: RockXQlibDataType = RockXQlibDataType.ANY
    required: bool = True
    description: str = ""
    default_value: Any = None

@dataclass
class RockXQlibExecutionResult:
    """执行结果"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    cache_hit: bool = False
    metadata: Dict[str, Any] = None
    ai_insights: List[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.ai_insights is None:
            self.ai_insights = []

class RockXQlibBaseNode(BaseNode):
    """RockXQlib基础节点类"""
    
    # 节点标识符
    __identifier__ = 'rockxqlib.base'
    NODE_NAME = 'RockXQlibBaseNode'
    
    def __init__(self):
        super().__init__()
        
        # 基础属性
        self._node_id = self._generate_node_id()
        self._status = RockXQlibNodeStatus.IDLE
        self._execution_context = {}
        self._thread_lock = threading.Lock()
        
        # 端口信息
        self._input_ports = {}
        self._output_ports = {}
        
        # 执行历史
        self._execution_history = []
        self._last_result = None
        
        # 性能统计
        self._execution_count = 0
        self._total_execution_time = 0.0
        self._cache_hit_count = 0
        self._ai_query_count = 0
        
        # 外部系统引用（延迟初始化）
        self._data_flow_manager = None
        self._message_bus = None
        self._ai_interface = None
        self._knowledge_base = None
        self._plugin_manager = None
        
        # 初始化节点
        self._initialize_node()
        
    def _generate_node_id(self) -> str:
        """生成节点ID"""
        timestamp = str(time.time())
        random_str = str(hash(self.__class__.__name__))
        return hashlib.md5(f"{timestamp}_{random_str}".encode()).hexdigest()[:12]
    
    def _initialize_node(self):
        """初始化节点"""
        try:
            # 设置节点基本属性
            self.set_name(self.__class__.__name__)
            self.set_color(100, 100, 100)  # 默认灰色
            
            # 添加基础属性
            self.add_text_input('node_id', '节点ID', self._node_id)
            self.add_text_input('description', '描述', f'{self.__class__.__name__}节点')
            self.add_checkbox('enable_cache', '启用缓存', '启用缓存', True)
            self.add_checkbox('enable_logging', '启用日志', '启用日志', True)
            self.add_checkbox('enable_ai', '启用AI', '启用AI', False)
            self.add_text_input('ai_prompt', 'AI提示', '请分析这个数据')
            
            # 初始化Qlib相关属性
            self._initialize_qlib_properties()
            
            # 初始化端口
            self._initialize_ports()
            
            # 初始化外部系统
            self._initialize_external_systems()
            
            logger.info(f"节点 {self.__class__.__name__} 初始化成功")
            
        except Exception as e:
            logger.error(f"节点 {self.__class__.__name__} 初始化失败: {e}")
            raise
    
    def _initialize_qlib_properties(self):
        """初始化Qlib相关属性"""
        if QLIB_AVAILABLE:
            # 添加Qlib配置属性
            # 默认路径自动探测，避免写死一个不存在的目录
            try:
                from qlib_paths import get_default_provider_uri
                _default_uri = get_default_provider_uri()
            except ImportError:
                try:
                    from core.qlib_paths import get_default_provider_uri
                    _default_uri = get_default_provider_uri()
                except ImportError:
                    _default_uri = '~/.qlib/qlib_data/cn_data'
            self.add_text_input('provider_uri', '数据路径', _default_uri)
            self.add_text_input('region', '地区', 'cn')
            self.add_checkbox('enable_recording', '启用记录', '启用记录', False)
            self.add_text_input('experiment_name', '实验名称', 'rockxqlib_experiment')
            self.add_text_input('recorder_name', '记录器名称', 'rockxqlib_recorder')
    
    def _initialize_ports(self):
        """初始化端口"""
        # 子类应该重写此方法来定义具体的端口
        pass
    
    def _initialize_external_systems(self):
        """初始化外部系统"""
        # 延迟初始化，避免循环导入
        pass
    
    def _get_data_flow_manager(self):
        """获取数据流管理器"""
        if self._data_flow_manager is None:
            from .data_flow import RockXQlibDataFlowManager
            self._data_flow_manager = RockXQlibDataFlowManager()
        return self._data_flow_manager
    
    def _get_message_bus(self):
        """获取消息总线"""
        if self._message_bus is None:
            from .message_system import RockXQlibMessageBus
            self._message_bus = RockXQlibMessageBus()
        return self._message_bus
    
    def _get_ai_interface(self):
        """获取AI接口"""
        if self._ai_interface is None:
            from .ai_integration import RockXQlibAIModelInterface
            self._ai_interface = RockXQlibAIModelInterface("gpt-3.5-turbo", {})
        return self._ai_interface
    
    def _get_knowledge_base(self):
        """获取知识库"""
        if self._knowledge_base is None:
            from .ai_integration import RockXQlibKnowledgeBase
            self._knowledge_base = RockXQlibKnowledgeBase()
        return self._knowledge_base
    
    def add_input_port(self, name: str, data_type: RockXQlibDataType = RockXQlibDataType.ANY, 
                      required: bool = True, description: str = "", default_value: Any = None):
        """添加输入端口"""
        port_info = RockXQlibPortInfo(name, RockXQlibPortType.INPUT, data_type, required, description, default_value)
        self._input_ports[name] = port_info
        self.add_input(name)
    
    def add_output_port(self, name: str, data_type: RockXQlibDataType = RockXQlibDataType.ANY, 
                       description: str = ""):
        """添加输出端口"""
        port_info = RockXQlibPortInfo(name, RockXQlibPortType.OUTPUT, data_type, description)
        self._output_ports[name] = port_info
        self.add_output(name)
    
    def validate_config(self) -> bool:
        """验证节点配置"""
        try:
            with self._thread_lock:
                # 验证基础配置
                if not self.get_rockx_property('node_id'):
                    logger.error("节点ID不能为空")
                    return False
                
                # 验证端口配置
                for port_name, port_info in self._input_ports.items():
                    if port_info.required:
                        # 检查必需的输入端口是否有数据
                        pass
                
                # 子类可以重写此方法添加特定的验证逻辑
                return self._validate_specific_config()
                
        except Exception as e:
            logger.error(f"配置验证失败: {e}")
            return False
    
    def _validate_specific_config(self) -> bool:
        """子类特定的配置验证"""
        return True
    
    def prepare_execution(self) -> bool:
        """准备执行环境"""
        try:
            with self._thread_lock:
                self._status = RockXQlibNodeStatus.RUNNING
                
                # 初始化Qlib环境
                if QLIB_AVAILABLE and self.get_rockx_property('enable_recording', False):
                    self._initialize_qlib_recording()
                
                # 子类特定的准备逻辑
                return self._prepare_specific_execution()
                
        except Exception as e:
            logger.error(f"执行准备失败: {e}")
            self._status = RockXQlibNodeStatus.FAILED
            return False
    
    def _initialize_qlib_recording(self):
        """初始化Qlib实验记录"""
        try:
            if QLIB_AVAILABLE:
                experiment_name = self.get_rockx_property('experiment_name', 'rockxqlib_experiment')
                recorder_name = self.get_rockx_property('recorder_name', 'rockxqlib_recorder')
                
                # 启动实验记录
                self._experiment = R.start(experiment_name=experiment_name, recorder_name=recorder_name)
                self._recorder = R.get_recorder()
                
                logger.info(f"Qlib实验记录已启动: {experiment_name}/{recorder_name}")
        except Exception as e:
            logger.warning(f"Qlib实验记录启动失败: {e}")
    
    def _prepare_specific_execution(self) -> bool:
        """子类特定的执行准备"""
        return True
    
    def execute(self, inputs: Dict[str, Any]) -> RockXQlibExecutionResult:
        """执行节点逻辑"""
        start_time = time.time()
        
        try:
            with self._thread_lock:
                # 准备执行
                if not self.prepare_execution():
                    return RockXQlibExecutionResult(
                        success=False,
                        error="执行准备失败",
                        execution_time=time.time() - start_time
                    )
                
                # 执行具体逻辑
                result_data = self._execute_logic(inputs)
                
                # AI分析（如果启用）
                ai_insights = []
                if self.get_rockx_property('enable_ai', False):
                    ai_insights = self._get_ai_insights(result_data, inputs)
                
                # 更新状态
                self._status = RockXQlibNodeStatus.COMPLETED
                self._last_result = result_data
                
                # 记录执行历史
                execution_time = time.time() - start_time
                self._execution_history.append({
                    'timestamp': time.time(),
                    'inputs': inputs,
                    'result': result_data,
                    'execution_time': execution_time,
                    'ai_insights': ai_insights
                })
                
                # 更新统计
                self._execution_count += 1
                self._total_execution_time += execution_time
                
                # 发送消息
                self._send_completion_message(result_data, execution_time)
                
                return RockXQlibExecutionResult(
                    success=True,
                    data=result_data,
                    execution_time=execution_time,
                    ai_insights=ai_insights,
                    metadata={
                        'node_id': self._node_id,
                        'execution_count': self._execution_count,
                        'status': self._status.value
                    }
                )
                
        except Exception as e:
            with self._thread_lock:
                self._status = RockXQlibNodeStatus.FAILED
                error_msg = f"节点执行失败: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                
                # 发送错误消息
                self._send_error_message(error_msg)
                
                return RockXQlibExecutionResult(
                    success=False,
                    error=error_msg,
                    execution_time=time.time() - start_time
                )
    
    @abstractmethod
    def _execute_logic(self, inputs: Dict[str, Any]) -> Any:
        """子类必须实现的具体执行逻辑"""
        pass
    
    def _get_ai_insights(self, data: Any, inputs: Dict[str, Any]) -> List[str]:
        """获取AI分析洞察"""
        try:
            if not self.get_rockx_property('enable_ai', False):
                return []
            
            ai_interface = self._get_ai_interface()
            prompt = self.get_rockx_property('ai_prompt', '请分析这个数据')
            
            # 构建AI查询
            query = f"{prompt}\n数据: {str(data)[:1000]}..."  # 限制数据长度
            insights = ai_interface.analyze_data(data, "insight")
            
            self._ai_query_count += 1
            return [insights] if isinstance(insights, str) else insights
            
        except Exception as e:
            logger.warning(f"AI分析失败: {e}")
            return []
    
    def _send_completion_message(self, result_data: Any, execution_time: float):
        """发送完成消息"""
        try:
            message_bus = self._get_message_bus()
            message = {
                'node_id': self._node_id,
                'status': 'completed',
                'execution_time': execution_time,
                'result_summary': str(result_data)[:200] if result_data else None
            }
            message_bus.publish(f"node.{self._node_id}.completed", message)
        except Exception as e:
            logger.warning(f"发送完成消息失败: {e}")
    
    def _send_error_message(self, error_msg: str):
        """发送错误消息"""
        try:
            message_bus = self._get_message_bus()
            message = {
                'node_id': self._node_id,
                'status': 'failed',
                'error': error_msg
            }
            message_bus.publish(f"node.{self._node_id}.error", message)
        except Exception as e:
            logger.warning(f"发送错误消息失败: {e}")
    
    def query_ai(self, query: str) -> str:
        """查询AI"""
        try:
            ai_interface = self._get_ai_interface()
            return ai_interface.generate_text(query)
        except Exception as e:
            logger.error(f"AI查询失败: {e}")
            return f"AI查询失败: {e}"
    
    def send_message(self, topic: str, message: Any):
        """发送消息"""
        try:
            message_bus = self._get_message_bus()
            message_bus.publish(topic, message)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
    
    def subscribe_message(self, topic: str, callback: Callable):
        """订阅消息"""
        try:
            message_bus = self._get_message_bus()
            message_bus.subscribe(topic, callback)
        except Exception as e:
            logger.error(f"订阅消息失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            with self._thread_lock:
                # 清理Qlib实验记录
                if hasattr(self, '_experiment') and self._experiment:
                    try:
                        self._experiment.__exit__(None, None, None)
                    except:
                        pass
                
                # 子类特定的清理逻辑
                self._cleanup_specific()
                
                logger.info(f"节点 {self.__class__.__name__} 资源清理完成")
                
        except Exception as e:
            logger.error(f"节点清理失败: {e}")
    
    def _cleanup_specific(self):
        """子类特定的清理逻辑"""
        pass
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        avg_execution_time = (self._total_execution_time / self._execution_count 
                            if self._execution_count > 0 else 0)
        
        return {
            'node_id': self._node_id,
            'node_type': self.__class__.__name__,
            'execution_count': self._execution_count,
            'total_execution_time': self._total_execution_time,
            'average_execution_time': avg_execution_time,
            'cache_hit_count': self._cache_hit_count,
            'ai_query_count': self._ai_query_count,
            'status': self._status.value,
            'last_result': self._last_result is not None
        }
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取执行历史"""
        return self._execution_history[-limit:]
    
    def reset_stats(self):
        """重置统计信息"""
        with self._thread_lock:
            self._execution_count = 0
            self._total_execution_time = 0.0
            self._cache_hit_count = 0
            self._ai_query_count = 0
            self._execution_history.clear()
            self._last_result = None
    
    def pause(self):
        """暂停节点"""
        with self._thread_lock:
            if self._status == RockXQlibNodeStatus.RUNNING:
                self._status = RockXQlibNodeStatus.PAUSED
    
    def resume(self):
        """恢复节点"""
        with self._thread_lock:
            if self._status == RockXQlibNodeStatus.PAUSED:
                self._status = RockXQlibNodeStatus.IDLE
    
    def __del__(self):
        """析构函数"""
        try:
            self.cleanup()
        except:
            pass
