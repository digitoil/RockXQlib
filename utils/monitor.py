#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 监控系统
"""

import time
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class RockXQlibMonitor:
    """系统监控器"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {}
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'uptime': time.time() - self.start_time
            }
        except Exception as e:
            logger.error(f"获取系统指标失败: {e}")
            return {}
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取监控指标"""
        return {
            'system': self.get_system_metrics(),
            'custom': self.metrics
        }
