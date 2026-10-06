#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qlib实验管理器
严格按照设计文档实现
"""

import os
import sys
import logging
import json
import time
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class QlibExperimentManager:
    """实验管理器"""
    
    def __init__(self, experiments_dir: str = "./experiments"):
        self.experiments_dir = experiments_dir
        self.experiments = {}
        self.current_experiment = None
        self.current_run = None
        self.experiment_config = {
            'auto_save': True,
            'save_artifacts': True,
            'save_metrics': True,
            'save_parameters': True,
            'max_experiments': 1000,
            'max_runs_per_experiment': 100
        }
        
        # 创建实验目录
        os.makedirs(experiments_dir, exist_ok=True)
        
        # 加载现有实验
        self._load_experiments()
        
        logger.info(f"实验管理器初始化完成: {experiments_dir}")
    
    def create_experiment(self, name: str, config: Dict) -> str:
        """创建实验"""
        try:
            # 生成实验ID
            experiment_id = str(uuid.uuid4())
            
            # 创建实验对象
            experiment = {
                'id': experiment_id,
                'name': name,
                'config': config,
                'created_time': datetime.now().isoformat(),
                'runs': {},
                'status': 'active',
                'description': config.get('description', ''),
                'tags': config.get('tags', []),
                'metrics': {},
                'artifacts': {}
            }
            
            # 保存实验
            self.experiments[experiment_id] = experiment
            self._save_experiment(experiment)
            
            logger.info(f"实验创建成功: {name} (ID: {experiment_id})")
            return experiment_id
            
        except Exception as e:
            logger.error(f"创建实验失败: {e}")
            return None
    
    def start_run(self, experiment_id: str, run_name: str) -> str:
        """开始运行"""
        try:
            if experiment_id not in self.experiments:
                logger.error(f"实验不存在: {experiment_id}")
                return None
            
            experiment = self.experiments[experiment_id]
            
            # 检查运行数量限制
            if len(experiment['runs']) >= self.experiment_config['max_runs_per_experiment']:
                logger.warning(f"实验运行数量已达上限: {experiment_id}")
                return None
            
            # 生成运行ID
            run_id = str(uuid.uuid4())
            
            # 创建运行对象
            run = {
                'id': run_id,
                'name': run_name,
                'experiment_id': experiment_id,
                'start_time': datetime.now().isoformat(),
                'end_time': None,
                'status': 'running',
                'parameters': {},
                'metrics': {},
                'artifacts': {},
                'logs': [],
                'error': None
            }
            
            # 添加到实验
            experiment['runs'][run_id] = run
            
            # 设置当前实验和运行
            self.current_experiment = experiment_id
            self.current_run = run_id
            
            # 保存实验
            if self.experiment_config['auto_save']:
                self._save_experiment(experiment)
            
            logger.info(f"运行开始: {run_name} (ID: {run_id})")
            return run_id
            
        except Exception as e:
            logger.error(f"开始运行失败: {e}")
            return None
    
    def end_run(self, run_id: str = None, status: str = 'completed', error: str = None):
        """结束运行"""
        try:
            if run_id is None:
                run_id = self.current_run
            
            if run_id is None:
                logger.error("没有活动的运行")
                return False
            
            # 获取运行
            run = self._get_run(run_id)
            if not run:
                logger.error(f"运行不存在: {run_id}")
                return False
            
            # 更新运行状态
            run['end_time'] = datetime.now().isoformat()
            run['status'] = status
            if error:
                run['error'] = error
            
            # 计算运行时间
            start_time = datetime.fromisoformat(run['start_time'])
            end_time = datetime.fromisoformat(run['end_time'])
            run['duration'] = (end_time - start_time).total_seconds()
            
            # 保存实验
            if self.experiment_config['auto_save']:
                experiment = self.experiments[run['experiment_id']]
                self._save_experiment(experiment)
            
            # 清除当前运行
            if self.current_run == run_id:
                self.current_run = None
            
            logger.info(f"运行结束: {run['name']} (状态: {status})")
            return True
            
        except Exception as e:
            logger.error(f"结束运行失败: {e}")
            return False
    
    def log_parameters(self, run_id: str, params: Dict):
        """记录参数"""
        try:
            if run_id is None:
                run_id = self.current_run
            
            if run_id is None:
                logger.error("没有活动的运行")
                return False
            
            # 获取运行
            run = self._get_run(run_id)
            if not run:
                logger.error(f"运行不存在: {run_id}")
                return False
            
            # 更新参数
            run['parameters'].update(params)
            
            # 保存实验
            if self.experiment_config['auto_save'] and self.experiment_config['save_parameters']:
                experiment = self.experiments[run['experiment_id']]
                self._save_experiment(experiment)
            
            logger.debug(f"参数记录成功: {run_id}, 参数数量: {len(params)}")
            return True
            
        except Exception as e:
            logger.error(f"记录参数失败: {e}")
            return False
    
    def log_metrics(self, run_id: str, metrics: Dict):
        """记录指标"""
        try:
            if run_id is None:
                run_id = self.current_run
            
            if run_id is None:
                logger.error("没有活动的运行")
                return False
            
            # 获取运行
            run = self._get_run(run_id)
            if not run:
                logger.error(f"运行不存在: {run_id}")
                return False
            
            # 更新指标
            run['metrics'].update(metrics)
            
            # 更新实验级别的指标
            experiment = self.experiments[run['experiment_id']]
            for key, value in metrics.items():
                if key not in experiment['metrics']:
                    experiment['metrics'][key] = []
                experiment['metrics'][key].append({
                    'run_id': run_id,
                    'value': value,
                    'timestamp': datetime.now().isoformat()
                })
            
            # 保存实验
            if self.experiment_config['auto_save'] and self.experiment_config['save_metrics']:
                self._save_experiment(experiment)
            
            logger.debug(f"指标记录成功: {run_id}, 指标数量: {len(metrics)}")
            return True
            
        except Exception as e:
            logger.error(f"记录指标失败: {e}")
            return False
    
    def log_artifacts(self, run_id: str, artifacts: Dict):
        """记录工件"""
        try:
            if run_id is None:
                run_id = self.current_run
            
            if run_id is None:
                logger.error("没有活动的运行")
                return False
            
            # 获取运行
            run = self._get_run(run_id)
            if not run:
                logger.error(f"运行不存在: {run_id}")
                return False
            
            # 更新工件
            run['artifacts'].update(artifacts)
            
            # 更新实验级别的工件
            experiment = self.experiments[run['experiment_id']]
            experiment['artifacts'].update(artifacts)
            
            # 保存工件到磁盘
            if self.experiment_config['save_artifacts']:
                self._save_artifacts(run['experiment_id'], run_id, artifacts)
            
            # 保存实验
            if self.experiment_config['auto_save']:
                self._save_experiment(experiment)
            
            logger.debug(f"工件记录成功: {run_id}, 工件数量: {len(artifacts)}")
            return True
            
        except Exception as e:
            logger.error(f"记录工件失败: {e}")
            return False
    
    def log_message(self, run_id: str, message: str, level: str = 'INFO'):
        """记录日志消息"""
        try:
            if run_id is None:
                run_id = self.current_run
            
            if run_id is None:
                logger.error("没有活动的运行")
                return False
            
            # 获取运行
            run = self._get_run(run_id)
            if not run:
                logger.error(f"运行不存在: {run_id}")
                return False
            
            # 添加日志消息
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'message': message
            }
            run['logs'].append(log_entry)
            
            # 保存实验
            if self.experiment_config['auto_save']:
                experiment = self.experiments[run['experiment_id']]
                self._save_experiment(experiment)
            
            return True
            
        except Exception as e:
            logger.error(f"记录日志消息失败: {e}")
            return False
    
    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """获取实验"""
        return self.experiments.get(experiment_id)
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取运行"""
        return self._get_run(run_id)
    
    def _get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """内部获取运行"""
        for experiment in self.experiments.values():
            if run_id in experiment['runs']:
                return experiment['runs'][run_id]
        return None
    
    def list_experiments(self) -> List[Dict[str, Any]]:
        """列出所有实验"""
        try:
            experiments_list = []
            for experiment in self.experiments.values():
                experiments_list.append({
                    'id': experiment['id'],
                    'name': experiment['name'],
                    'created_time': experiment['created_time'],
                    'status': experiment['status'],
                    'run_count': len(experiment['runs']),
                    'description': experiment['description'],
                    'tags': experiment['tags']
                })
            
            # 按创建时间排序
            experiments_list.sort(key=lambda x: x['created_time'], reverse=True)
            
            return experiments_list
            
        except Exception as e:
            logger.error(f"列出实验失败: {e}")
            return []
    
    def list_runs(self, experiment_id: str = None) -> List[Dict[str, Any]]:
        """列出运行"""
        try:
            runs_list = []
            
            if experiment_id:
                # 列出特定实验的运行
                if experiment_id in self.experiments:
                    experiment = self.experiments[experiment_id]
                    for run in experiment['runs'].values():
                        runs_list.append({
                            'id': run['id'],
                            'name': run['name'],
                            'experiment_id': run['experiment_id'],
                            'start_time': run['start_time'],
                            'end_time': run['end_time'],
                            'status': run['status'],
                            'duration': run.get('duration', 0)
                        })
            else:
                # 列出所有运行
                for experiment in self.experiments.values():
                    for run in experiment['runs'].values():
                        runs_list.append({
                            'id': run['id'],
                            'name': run['name'],
                            'experiment_id': run['experiment_id'],
                            'start_time': run['start_time'],
                            'end_time': run['end_time'],
                            'status': run['status'],
                            'duration': run.get('duration', 0)
                        })
            
            # 按开始时间排序
            runs_list.sort(key=lambda x: x['start_time'], reverse=True)
            
            return runs_list
            
        except Exception as e:
            logger.error(f"列出运行失败: {e}")
            return []
    
    def compare_runs(self, run_ids: List[str]) -> Dict[str, Any]:
        """比较运行"""
        try:
            if len(run_ids) < 2:
                logger.error("至少需要2个运行进行比较")
                return {}
            
            comparison = {
                'run_ids': run_ids,
                'parameters': {},
                'metrics': {},
                'artifacts': {}
            }
            
            # 获取运行数据
            runs = []
            for run_id in run_ids:
                run = self._get_run(run_id)
                if run:
                    runs.append(run)
                else:
                    logger.warning(f"运行不存在: {run_id}")
            
            if len(runs) < 2:
                logger.error("有效的运行数量不足")
                return {}
            
            # 比较参数
            all_params = set()
            for run in runs:
                all_params.update(run['parameters'].keys())
            
            for param in all_params:
                comparison['parameters'][param] = {}
                for run in runs:
                    comparison['parameters'][param][run['id']] = run['parameters'].get(param, None)
            
            # 比较指标
            all_metrics = set()
            for run in runs:
                all_metrics.update(run['metrics'].keys())
            
            for metric in all_metrics:
                comparison['metrics'][metric] = {}
                for run in runs:
                    comparison['metrics'][metric][run['id']] = run['metrics'].get(metric, None)
            
            # 比较工件
            all_artifacts = set()
            for run in runs:
                all_artifacts.update(run['artifacts'].keys())
            
            for artifact in all_artifacts:
                comparison['artifacts'][artifact] = {}
                for run in runs:
                    comparison['artifacts'][artifact][run['id']] = run['artifacts'].get(artifact, None)
            
            logger.info(f"运行比较完成: {len(run_ids)} 个运行")
            return comparison
            
        except Exception as e:
            logger.error(f"比较运行失败: {e}")
            return {}
    
    def delete_experiment(self, experiment_id: str) -> bool:
        """删除实验"""
        try:
            if experiment_id not in self.experiments:
                logger.error(f"实验不存在: {experiment_id}")
                return False
            
            # 删除实验文件
            experiment_file = os.path.join(self.experiments_dir, f"{experiment_id}.json")
            if os.path.exists(experiment_file):
                os.remove(experiment_file)
            
            # 删除工件目录
            artifacts_dir = os.path.join(self.experiments_dir, experiment_id)
            if os.path.exists(artifacts_dir):
                import shutil
                shutil.rmtree(artifacts_dir)
            
            # 从内存中删除
            del self.experiments[experiment_id]
            
            # 清除当前实验
            if self.current_experiment == experiment_id:
                self.current_experiment = None
                self.current_run = None
            
            logger.info(f"实验删除成功: {experiment_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除实验失败: {e}")
            return False
    
    def _save_experiment(self, experiment: Dict[str, Any]):
        """保存实验"""
        try:
            experiment_file = os.path.join(self.experiments_dir, f"{experiment['id']}.json")
            
            with open(experiment_file, 'w', encoding='utf-8') as f:
                json.dump(experiment, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"保存实验失败: {e}")
    
    def _save_artifacts(self, experiment_id: str, run_id: str, artifacts: Dict[str, Any]):
        """保存工件"""
        try:
            artifacts_dir = os.path.join(self.experiments_dir, experiment_id, run_id)
            os.makedirs(artifacts_dir, exist_ok=True)
            
            for artifact_name, artifact_data in artifacts.items():
                artifact_file = os.path.join(artifacts_dir, f"{artifact_name}.json")
                
                with open(artifact_file, 'w', encoding='utf-8') as f:
                    json.dump(artifact_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"保存工件失败: {e}")
    
    def _load_experiments(self):
        """加载现有实验"""
        try:
            for filename in os.listdir(self.experiments_dir):
                if filename.endswith('.json') and filename != 'config.json':
                    experiment_file = os.path.join(self.experiments_dir, filename)
                    
                    with open(experiment_file, 'r', encoding='utf-8') as f:
                        experiment = json.load(f)
                    
                    self.experiments[experiment['id']] = experiment
            
            logger.info(f"加载了 {len(self.experiments)} 个实验")
            
        except Exception as e:
            logger.error(f"加载实验失败: {e}")
    
    def get_experiment_stats(self) -> Dict[str, Any]:
        """获取实验统计信息"""
        try:
            total_experiments = len(self.experiments)
            total_runs = sum(len(exp['runs']) for exp in self.experiments.values())
            
            # 按状态统计
            status_counts = {}
            for experiment in self.experiments.values():
                status = experiment['status']
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # 按状态统计运行
            run_status_counts = {}
            for experiment in self.experiments.values():
                for run in experiment['runs'].values():
                    status = run['status']
                    run_status_counts[status] = run_status_counts.get(status, 0) + 1
            
            return {
                'total_experiments': total_experiments,
                'total_runs': total_runs,
                'experiment_status_counts': status_counts,
                'run_status_counts': run_status_counts,
                'current_experiment': self.current_experiment,
                'current_run': self.current_run
            }
            
        except Exception as e:
            logger.error(f"获取实验统计失败: {e}")
            return {}
    
    def cleanup_old_experiments(self, max_age_days: int = 30):
        """清理旧实验"""
        try:
            current_time = datetime.now()
            deleted_count = 0
            
            for experiment_id, experiment in list(self.experiments.items()):
                created_time = datetime.fromisoformat(experiment['created_time'])
                age_days = (current_time - created_time).days
                
                if age_days > max_age_days:
                    if self.delete_experiment(experiment_id):
                        deleted_count += 1
            
            logger.info(f"清理了 {deleted_count} 个旧实验")
            return deleted_count
            
        except Exception as e:
            logger.error(f"清理旧实验失败: {e}")
            return 0
