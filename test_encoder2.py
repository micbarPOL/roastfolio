import json
import math
from decimal import Decimal

class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        return super().default(o)

    def encode(self, obj):
        # We also sanitize NaN/Infinity floats because json.dumps allows them by default 
        # (producing invalid JSON strings like NaN instead of null)
        obj = self._sanitize(obj)
        return super().encode(obj)

    @staticmethod
    def _sanitize(obj):
        if isinstance(obj, float):
            return None if (math.isnan(obj) or math.isinf(obj)) else obj
        if isinstance(obj, dict):
            return {k: _DecimalEncoder._sanitize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_DecimalEncoder._sanitize(v) for v in obj]
        return obj

print(json.dumps({"a": Decimal("NaN")}, cls=_DecimalEncoder))
