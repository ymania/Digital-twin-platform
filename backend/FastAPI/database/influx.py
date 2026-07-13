"""
Digital Twin Backend — InfluxDB Client

使用同步 SYNCHRONOUS 写入模式，强制打印每步状态。
"""
import os
import logging
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger("dt.influxdb")

_client: influxdb_client.InfluxDBClient | None = None
_write_api = None


def get_client() -> influxdb_client.InfluxDBClient:
    global _client
    if _client is None:
        url = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
        token = os.getenv("INFLUXDB_TOKEN", "dt_influx_token_2025")
        org = os.getenv("INFLUXDB_ORG", "dt_platform")
        logger.info("InfluxDB connecting: url=%s org=%s", url, org)
        _client = influxdb_client.InfluxDBClient(
            url=url,
            token=token,
            org=org,
            debug=True,  # ★ 开启 debug 打印底层 HTTP 请求
        )
        # 验证连通性
        try:
            ping = _client.ping()
            logger.info("InfluxDB ping: %s", ping)
        except Exception as e:
            logger.error("InfluxDB ping FAILED: %s", e)
    return _client


def write_api():
    global _write_api
    if _write_api is None:
        _write_api = get_client().write_api(write_options=SYNCHRONOUS)
        logger.info("InfluxDB write_api initialized (SYNCHRONOUS)")
    return _write_api


def query_api():
    return get_client().query_api()


def close():
    global _client, _write_api
    if _client:
        _client.close()
        _client = None
        _write_api = None
