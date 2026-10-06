#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RockXQlib 向量数据库
基于Faiss的高性能向量数据库，用于知识库和相似性搜索
"""

import os
import time
import json
import logging
import threading
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("Faiss未安装，向量数据库功能将不可用")

class RockXQlibIndexType(Enum):
    """索引类型枚举"""
    FLAT = "flat"  # 精确搜索
    IVF = "ivf"    # 倒排索引
    HNSW = "hnsw"  # 层次化小世界图
    PQ = "pq"      # 乘积量化

@dataclass
class RockXQlibVectorItem:
    """向量项"""
    vector_id: str
    vector: np.ndarray
    text: str
    metadata: Dict[str, Any] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = time.time()

class RockXQlibVectorDatabase:
    """基于Faiss的向量数据库"""
    
    def __init__(self, dimension: int = 768, index_type: RockXQlibIndexType = RockXQlibIndexType.FLAT,
                 persist_path: Optional[str] = None):
        if not FAISS_AVAILABLE:
            raise ImportError("Faiss未安装，无法使用向量数据库功能")
        
        self.dimension = dimension
        self.index_type = index_type
        self.persist_path = persist_path or "vector_db"
        
        # 向量存储
        self.index = None
        self.vector_items = {}  # vector_id -> VectorItem
        self.text_to_id = {}    # text -> vector_id
        self.id_to_text = {}    # vector_id -> text
        
        # 统计信息
        self.total_vectors = 0
        self.total_searches = 0
        self.start_time = time.time()
        
        # 线程锁
        self.lock = threading.Lock()
        
        # 初始化索引
        self._initialize_index()
        
        # 加载持久化数据
        self._load_persisted_data()
    
    def _initialize_index(self):
        """初始化Faiss索引"""
        try:
            if self.index_type == RockXQlibIndexType.FLAT:
                # 精确搜索索引
                self.index = faiss.IndexFlatIP(self.dimension)  # 内积相似度
            elif self.index_type == RockXQlibIndexType.IVF:
                # 倒排索引
                quantizer = faiss.IndexFlatIP(self.dimension)
                self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            elif self.index_type == RockXQlibIndexType.HNSW:
                # 层次化小世界图
                self.index = faiss.IndexHNSWFlat(self.dimension, 32)
            elif self.index_type == RockXQlibIndexType.PQ:
                # 乘积量化
                self.index = faiss.IndexPQ(self.dimension, 8, 8)
            else:
                raise ValueError(f"不支持的索引类型: {self.index_type}")
            
            logger.info(f"向量索引初始化成功: {self.index_type.value}, 维度: {self.dimension}")
            
        except Exception as e:
            logger.error(f"初始化向量索引失败: {e}")
            raise
    
    def _load_persisted_data(self):
        """加载持久化数据"""
        try:
            if not os.path.exists(self.persist_path):
                os.makedirs(self.persist_path, exist_ok=True)
                return
            
            # 加载向量数据
            vectors_file = os.path.join(self.persist_path, "vectors.pkl")
            if os.path.exists(vectors_file):
                with open(vectors_file, 'rb') as f:
                    self.vector_items = pickle.load(f)
                
                # 重建索引
                if self.vector_items:
                    vectors = np.array([item.vector for item in self.vector_items.values()])
                    self.index.add(vectors)
                    
                    # 重建映射
                    for vector_id, item in self.vector_items.items():
                        self.text_to_id[item.text] = vector_id
                        self.id_to_text[vector_id] = item.text
                    
                    self.total_vectors = len(self.vector_items)
                    logger.info(f"加载了 {self.total_vectors} 个向量")
            
        except Exception as e:
            logger.error(f"加载持久化数据失败: {e}")
    
    def _save_persisted_data(self):
        """保存持久化数据"""
        try:
            with self.lock:
                vectors_file = os.path.join(self.persist_path, "vectors.pkl")
                with open(vectors_file, 'wb') as f:
                    pickle.dump(self.vector_items, f)
                
                # 保存索引
                index_file = os.path.join(self.persist_path, "index.faiss")
                faiss.write_index(self.index, index_file)
                
                logger.debug("向量数据已保存")
                
        except Exception as e:
            logger.error(f"保存持久化数据失败: {e}")
    
    def add_vector(self, vector: np.ndarray, text: str, metadata: Optional[Dict[str, Any]] = None,
                  vector_id: Optional[str] = None) -> str:
        """添加向量"""
        try:
            if vector.shape[0] != self.dimension:
                raise ValueError(f"向量维度不匹配: 期望 {self.dimension}, 实际 {vector.shape[0]}")
            
            # 生成向量ID
            if vector_id is None:
                vector_id = f"vec_{int(time.time() * 1000000)}"
            
            # 检查是否已存在
            if vector_id in self.vector_items:
                logger.warning(f"向量ID {vector_id} 已存在，将更新")
            
            with self.lock:
                # 创建向量项
                vector_item = RockXQlibVectorItem(
                    vector_id=vector_id,
                    vector=vector.astype(np.float32),
                    text=text,
                    metadata=metadata or {},
                    timestamp=time.time()
                )
                
                # 添加到存储
                self.vector_items[vector_id] = vector_item
                self.text_to_id[text] = vector_id
                self.id_to_text[vector_id] = text
                
                # 添加到索引
                self.index.add(vector.reshape(1, -1).astype(np.float32))
                
                self.total_vectors += 1
            
            # 定期保存
            if self.total_vectors % 100 == 0:
                self._save_persisted_data()
            
            logger.debug(f"向量 {vector_id} 添加成功")
            return vector_id
            
        except Exception as e:
            logger.error(f"添加向量失败: {e}")
            raise
    
    def add_vectors_batch(self, vectors: np.ndarray, texts: List[str], 
                         metadata_list: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """批量添加向量"""
        try:
            if len(vectors) != len(texts):
                raise ValueError("向量数量与文本数量不匹配")
            
            if vectors.shape[1] != self.dimension:
                raise ValueError(f"向量维度不匹配: 期望 {self.dimension}, 实际 {vectors.shape[1]}")
            
            vector_ids = []
            
            with self.lock:
                for i, (vector, text) in enumerate(zip(vectors, texts)):
                    vector_id = f"vec_{int(time.time() * 1000000)}_{i}"
                    metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else {}
                    
                    # 创建向量项
                    vector_item = RockXQlibVectorItem(
                        vector_id=vector_id,
                        vector=vector.astype(np.float32),
                        text=text,
                        metadata=metadata,
                        timestamp=time.time()
                    )
                    
                    # 添加到存储
                    self.vector_items[vector_id] = vector_item
                    self.text_to_id[text] = vector_id
                    self.id_to_text[vector_id] = text
                    
                    vector_ids.append(vector_id)
                
                # 批量添加到索引
                self.index.add(vectors.astype(np.float32))
                self.total_vectors += len(vectors)
            
            # 保存数据
            self._save_persisted_data()
            
            logger.info(f"批量添加了 {len(vectors)} 个向量")
            return vector_ids
            
        except Exception as e:
            logger.error(f"批量添加向量失败: {e}")
            raise
    
    def search(self, query_vector: np.ndarray, k: int = 10, 
               filter_func: Optional[callable] = None) -> List[Dict[str, Any]]:
        """搜索相似向量"""
        try:
            if query_vector.shape[0] != self.dimension:
                raise ValueError(f"查询向量维度不匹配: 期望 {self.dimension}, 实际 {query_vector.shape[0]}")
            
            if self.total_vectors == 0:
                return []
            
            # 确保索引已训练
            if hasattr(self.index, 'is_trained') and not self.index.is_trained:
                logger.warning("索引未训练，将使用所有向量进行训练")
                if self.total_vectors > 0:
                    vectors = np.array([item.vector for item in self.vector_items.values()])
                    self.index.train(vectors)
            
            # 搜索
            query_vector = query_vector.reshape(1, -1).astype(np.float32)
            scores, indices = self.index.search(query_vector, min(k, self.total_vectors))
            
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:  # 无效索引
                    continue
                
                # 获取向量项
                vector_ids = list(self.vector_items.keys())
                if idx < len(vector_ids):
                    vector_id = vector_ids[idx]
                    vector_item = self.vector_items[vector_id]
                    
                    # 应用过滤器
                    if filter_func and not filter_func(vector_item):
                        continue
                    
                    results.append({
                        'vector_id': vector_id,
                        'text': vector_item.text,
                        'score': float(score),
                        'metadata': vector_item.metadata,
                        'timestamp': vector_item.timestamp
                    })
            
            self.total_searches += 1
            logger.debug(f"搜索完成，返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"搜索向量失败: {e}")
            return []
    
    def search_by_text(self, text: str, k: int = 10) -> List[Dict[str, Any]]:
        """通过文本搜索相似向量"""
        try:
            # 这里需要文本向量化，可以使用预训练模型
            # 暂时返回空结果，实际应用中需要集成文本向量化模型
            logger.warning("文本搜索功能需要集成文本向量化模型")
            return []
            
        except Exception as e:
            logger.error(f"文本搜索失败: {e}")
            return []
    
    def get_vector(self, vector_id: str) -> Optional[RockXQlibVectorItem]:
        """获取向量项"""
        with self.lock:
            return self.vector_items.get(vector_id)
    
    def delete_vector(self, vector_id: str) -> bool:
        """删除向量"""
        try:
            with self.lock:
                if vector_id not in self.vector_items:
                    return False
                
                vector_item = self.vector_items[vector_id]
                
                # 从映射中删除
                if vector_item.text in self.text_to_id:
                    del self.text_to_id[vector_item.text]
                if vector_id in self.id_to_text:
                    del self.id_to_text[vector_id]
                
                # 从存储中删除
                del self.vector_items[vector_id]
                
                # 注意：Faiss索引不支持删除单个向量，需要重建索引
                # 这里简化处理，实际应用中可能需要更复杂的索引管理
                self.total_vectors -= 1
                
                logger.info(f"向量 {vector_id} 删除成功")
                return True
                
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
            return False
    
    def update_vector(self, vector_id: str, vector: Optional[np.ndarray] = None,
                     text: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新向量"""
        try:
            with self.lock:
                if vector_id not in self.vector_items:
                    return False
                
                vector_item = self.vector_items[vector_id]
                
                # 更新字段
                if vector is not None:
                    if vector.shape[0] != self.dimension:
                        raise ValueError(f"向量维度不匹配: 期望 {self.dimension}, 实际 {vector.shape[0]}")
                    vector_item.vector = vector.astype(np.float32)
                
                if text is not None:
                    # 更新文本映射
                    if vector_item.text in self.text_to_id:
                        del self.text_to_id[vector_item.text]
                    vector_item.text = text
                    self.text_to_id[text] = vector_id
                    self.id_to_text[vector_id] = text
                
                if metadata is not None:
                    vector_item.metadata.update(metadata)
                
                vector_item.timestamp = time.time()
                
                # 注意：Faiss索引不支持更新单个向量，需要重建索引
                # 这里简化处理，实际应用中可能需要更复杂的索引管理
                
                logger.info(f"向量 {vector_id} 更新成功")
                return True
                
        except Exception as e:
            logger.error(f"更新向量失败: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            uptime = time.time() - self.start_time
            return {
                'dimension': self.dimension,
                'index_type': self.index_type.value,
                'total_vectors': self.total_vectors,
                'total_searches': self.total_searches,
                'uptime': uptime,
                'searches_per_minute': self.total_searches / max(uptime / 60, 1),
                'is_trained': getattr(self.index, 'is_trained', True) if hasattr(self.index, 'is_trained') else True
            }
    
    def rebuild_index(self):
        """重建索引"""
        try:
            with self.lock:
                if not self.vector_items:
                    logger.warning("没有向量数据，无法重建索引")
                    return
                
                # 重新初始化索引
                self._initialize_index()
                
                # 重新添加所有向量
                vectors = np.array([item.vector for item in self.vector_items.values()])
                self.index.add(vectors)
                
                logger.info("索引重建完成")
                
        except Exception as e:
            logger.error(f"重建索引失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            # 保存数据
            self._save_persisted_data()
            logger.info("向量数据库清理完成")
        except Exception as e:
            logger.error(f"向量数据库清理失败: {e}")

class RockXQlibTextVectorizer:
    """文本向量化器"""
    
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self._initialize_model()
    
    def _initialize_model(self):
        """初始化文本向量化模型"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"文本向量化模型 {self.model_name} 初始化成功")
        except ImportError:
            logger.warning("sentence-transformers未安装，文本向量化功能不可用")
        except Exception as e:
            logger.error(f"初始化文本向量化模型失败: {e}")
    
    def encode_text(self, text: str) -> np.ndarray:
        """将文本编码为向量"""
        try:
            if self.model is None:
                raise RuntimeError("文本向量化模型未初始化")
            
            vector = self.model.encode([text])
            return vector[0]
            
        except Exception as e:
            logger.error(f"文本向量化失败: {e}")
            return np.zeros(384)  # 默认维度
    
    def encode_texts(self, texts: List[str]) -> np.ndarray:
        """批量编码文本为向量"""
        try:
            if self.model is None:
                raise RuntimeError("文本向量化模型未初始化")
            
            vectors = self.model.encode(texts)
            return vectors
            
        except Exception as e:
            logger.error(f"批量文本向量化失败: {e}")
            return np.zeros((len(texts), 384))  # 默认维度
