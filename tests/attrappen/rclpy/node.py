# Attrappe von rclpy.node.Node: merkt sich Parameter, Abos und Publisher.
class _Log:
    def info(self, *a, **k): pass
    warn = error = info
class _Pub:
    def __init__(self, t): self.t = t; self.n = 0; self.letzte = None
    def publish(self, m): self.n += 1; self.letzte = m
class _Wert:
    def __init__(self, v): self.value = v
class Node:
    def __init__(self, name, **k): self.subs = {}; self.pubs = {}; self._p = {}; self._cbs = []
    def declare_parameter(self, n, v): self._p[n] = v
    def get_parameter(self, n): return _Wert(self._p[n])
    def set_parameters(self, liste):
        for cb in self._cbs: cb(liste)
        for p in liste: self._p[p.name] = p.value
    def add_on_set_parameters_callback(self, cb): self._cbs.append(cb)
    def create_publisher(self, typ, topic, q, **k): self.pubs[topic] = _Pub(topic); return self.pubs[topic]
    def create_subscription(self, typ, topic, cb, q, **k): self.subs[topic] = cb; return cb
    def destroy_subscription(self, s): pass
    def create_timer(self, p, cb, **k): return None
    def get_logger(self): return _Log()
    def get_node_names(self): return ['YB_Node', 'joy_node']
    def get_topic_names_and_types(self): return []
    def count_publishers(self, t): return 1
    def destroy_node(self): pass
