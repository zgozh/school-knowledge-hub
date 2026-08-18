# ADR-002: 向量库选型 Milvus（复用已有服务）

- 日期：2026-08-18
- 状态：已接受

## 背景
检索链路需要 dense+sparse 双向量混合检索（BGE-M3 双输出）。用户已有 Milvus 服务（DocMind 项目部署），复用优先。

## 决策
使用 Milvus standalone：dense COSINE + sparse IP 同集合混合检索。复用用户已有部署经验与 DocMind 实证链路。

## 备选
- Qdrant：sparse 支持完善，但需新装且无既有经验。
- LanceDB：零服务嵌入式最省事，但"中台"叙事弱、无既有经验。
- Chroma：sparse 支持弱——否决。

## 后果
- 正面：官方 BGE-M3 双输出示例一手支持；用户既有运维经验直接复用。
- 重新评估触发：若单机资源紧张或部署频繁失败，降级考虑 LanceDB 嵌入式。

## 人工资源依赖
Milvus 镜像需提前 `docker pull`；最终统一编入项目 docker-compose（开发期可用 WSL 现有服务）。
