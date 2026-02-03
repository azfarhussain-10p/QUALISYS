# ElastiCache Parameter Group
# Story: 0-5 Redis Caching Layer
# AC: 9 - Eviction policy: allkeys-lru
# Tasks 3.1-3.5

resource "aws_elasticache_parameter_group" "redis7" {
  name        = "${var.project_name}-redis7"
  family      = "redis7"
  description = "Custom Redis 7 parameter group for QUALISYS"

  # Task 3.2 - allkeys-lru eviction policy (AC9)
  # Evict least recently used keys when memory is full
  parameter {
    name  = "maxmemory-policy"
    value = "allkeys-lru"
  }

  # Task 3.3 - TCP keepalive for connection health checks (300 seconds)
  parameter {
    name  = "tcp-keepalive"
    value = "300"
  }

  # Task 3.4 - No idle timeout for persistent application connections
  parameter {
    name  = "timeout"
    value = "0"
  }

  # Task 3.5 - Keyspace notifications for cache monitoring
  # E = keyevent notification class, x = expired events, e = evicted events
  parameter {
    name  = "notify-keyspace-events"
    value = "Exe"
  }

  # Cluster mode enabled (required for num_node_groups in replication group)
  parameter {
    name  = "cluster-enabled"
    value = "yes"
  }

  tags = {
    Name = "${var.project_name}-redis7-params"
  }
}
