#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NodeGraphQt 节点样式配置
基于深色主题的节点样式设置
"""

from dark_theme_styles import DarkThemeStyles

class NodeStylesConfig:
    """节点样式配置类"""
    
    @staticmethod
    def get_node_color_config():
        """获取节点颜色配置"""
        return {
            # 基础节点颜色
            'default': {
                'color': (44, 44, 44),           # 节点背景色 #2c2c2c
                'border_color': (74, 74, 74),    # 节点边框色 #4a4a4a
                'text_color': (255, 255, 255),   # 节点文本色 #ffffff
                'selected_border_color': (224, 224, 224),  # 选中边框色 #e0e0e0
            },
            
            # Qlib核心节点
            'qlib_core': {
                'color': (52, 73, 94),           # 深蓝灰色 #34495e
                'border_color': (44, 62, 80),    # 深蓝灰边框 #2c3e50
                'text_color': (236, 240, 241),   # 浅灰文本 #ecf0f1
                'selected_border_color': (52, 152, 219),  # 蓝色选中 #3498db
            },
            
            # AI功能节点
            'ai_function': {
                'color': (46, 125, 50),          # 深绿色 #2e7d32
                'border_color': (27, 94, 32),    # 深绿边框 #1b5e20
                'text_color': (255, 255, 255),   # 白色文本
                'selected_border_color': (76, 175, 80),  # 绿色选中 #4caf50
            },
            
            # 可视化节点
            'visualization': {
                'color': (156, 39, 176),         # 紫色 #9c27b0
                'border_color': (123, 31, 162),  # 深紫边框 #7b1fa2
                'text_color': (255, 255, 255),   # 白色文本
                'selected_border_color': (186, 104, 200),  # 浅紫选中 #ba68c8
            },
            
            # Kronos模型节点
            'kronos_model': {
                'color': (255, 87, 34),          # 橙色 #ff5722
                'border_color': (230, 81, 0),    # 深橙边框 #e65100
                'text_color': (255, 255, 255),   # 白色文本
                'selected_border_color': (255, 183, 77),  # 浅橙选中 #ffb74d
            },
            
            # 核心集成节点
            'core_integration': {
                'color': (63, 81, 181),          # 靛蓝色 #3f51b5
                'border_color': (48, 63, 159),   # 深靛边框 #303f9f
                'text_color': (255, 255, 255),   # 白色文本
                'selected_border_color': (121, 134, 203),  # 浅靛选中 #7986cb
            },
            
            # 工作流控制节点
            'workflow_control': {
                'color': (96, 125, 139),         # 蓝灰色 #607d8b
                'border_color': (69, 90, 120),   # 深蓝灰边框 #455a64
                'text_color': (255, 255, 255),   # 白色文本
                'selected_border_color': (144, 164, 174),  # 浅蓝灰选中 #90a4ae
            }
        }
    
    @staticmethod
    def get_port_style_config():
        """获取端口样式配置"""
        return {
            'input_port': {
                'color': (58, 58, 58),           # 输入端口背景 #3a3a3a
                'border_color': (74, 74, 74),    # 输入端口边框 #4a4a4a
                'hover_color': (52, 152, 219),   # 悬停色 #3498db
                'text_color': (255, 255, 255),   # 端口文本色
            },
            'output_port': {
                'color': (58, 58, 58),           # 输出端口背景 #3a3a3a
                'border_color': (74, 74, 74),    # 输出端口边框 #4a4a4a
                'hover_color': (52, 152, 219),   # 悬停色 #3498db
                'text_color': (255, 255, 255),   # 端口文本色
            }
        }
    
    @staticmethod
    def get_connection_style_config():
        """获取连接线样式配置"""
        return {
            'default_connection': {
                'color': (243, 156, 18),         # 橙色连接线 #f39c12
                'width': 2,                      # 连接线宽度
                'hover_color': (230, 126, 34),   # 悬停色 #e67e22
                'selected_color': (52, 152, 219), # 选中色 #3498db
            },
            'data_connection': {
                'color': (243, 156, 18),         # 数据连接 - 橙色
                'width': 2,
                'hover_color': (230, 126, 34),
                'selected_color': (52, 152, 219),
            },
            'control_connection': {
                'color': (155, 89, 182),         # 控制连接 - 紫色
                'width': 2,
                'hover_color': (142, 68, 173),
                'selected_color': (52, 152, 219),
            }
        }
    
    @staticmethod
    def apply_node_style(node, node_type='default'):
        """应用节点样式"""
        try:
            color_config = NodeStylesConfig.get_node_color_config()
            if node_type in color_config:
                config = color_config[node_type]
            else:
                config = color_config['default']
            
            # 设置节点颜色
            node.set_color(*config['color'])
            node.set_border_color(*config['border_color'])
            node.set_text_color(*config['text_color'])
            
            # 设置选中状态颜色
            if hasattr(node, 'set_selected_border_color'):
                node.set_selected_border_color(*config['selected_border_color'])
            
            return True
        except Exception as e:
            print(f"❌ 应用节点样式失败: {e}")
            return False
    
    @staticmethod
    def get_node_type_from_category(category):
        """根据节点类别获取样式类型"""
        category_mapping = {
            'qlib_core': 'qlib_core',
            'ai_function': 'ai_function', 
            'visualization': 'visualization',
            'kronos_model': 'kronos_model',
            'core_integration': 'core_integration',
            'workflow_control': 'workflow_control'
        }
        return category_mapping.get(category, 'default')
    
    @staticmethod
    def setup_graph_styles(graph):
        """设置图形样式"""
        try:
            if not graph:
                return False
            
            # 设置背景色
            graph.set_background_color(26, 26, 26)  # #1a1a1a
            
            # 设置网格
            if hasattr(graph, 'set_grid_mode'):
                graph.set_grid_mode(True)
            
            # 设置网格大小和颜色
            try:
                graph.set_grid_size(20)
            except AttributeError:
                pass
            
            try:
                graph.set_grid_color(64, 64, 64)  # 深灰色网格 #404040
            except AttributeError:
                pass
            
            print("✅ 图形样式设置完成")
            return True
            
        except Exception as e:
            print(f"❌ 图形样式设置失败: {e}")
            return False


# 导出配置类
__all__ = ['NodeStylesConfig']
