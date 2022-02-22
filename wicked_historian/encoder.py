import json


JSON_NULL = object()


class JSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if obj is JSON_NULL:
            return None
        return super(JSONEncoder, self).default(obj)
