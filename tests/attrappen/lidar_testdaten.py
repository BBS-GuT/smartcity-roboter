"""Explicit synthetic geometry for software controls, never product defaults.

These scans already use base_link. The small test vehicle is deliberately not
RM01 or a factory model; 10-cm targets lie outside its six-centimetre front/rear.
A real vehicle needs measured
individual parameters instead of these synthetic values.
"""


def geometrie(node, hull=(.06, .06, .06, .06)):
    count = len(node.p('scan_topics'))
    node._p.update(scan_frames=['base_link'] * count,
                   scan_einbau_xy=[0.0] * (2 * count),
                   scan_einbau_quelle=['gemessen'] * count,
                   fahrzeug_grenzen=list(hull))
