import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "MCP"))
from hive_executor import HiveExecutor
executor = HiveExecutor(str(BASE_DIR / "MCP" / "hive_config.yaml"))
conn = executor._get_connection()
cursor = conn.cursor()
for mem in ["5g", "8g", "10g", "20g"]:
    try:
        cursor.execute(f"SET MEM_LIMIT={mem}")
        print(f"SET MEM_LIMIT={mem} SUCCESS")
    except Exception as e:
        print(f"SET MEM_LIMIT={mem} FAILED: {e}")
cursor.close()
conn.close()
