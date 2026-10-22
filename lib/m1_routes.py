"""Advisory route ranking. No driving, stopping or motor permissions here."""
import time


def choose(allowed_exits, own_robot, own_section, peers, original_choice,
           *, map_id, map_version, now=None, max_age_s=3):
    """Return one already allowed exit; stale/bad data returns local choice."""
    allowed = tuple(allowed_exits)
    if not allowed or original_choice not in allowed:
        raise ValueError('original choice must be locally allowed')
    current = time.time() if now is None else now
    fresh = []
    for peer in peers:
        if (peer.get('robot') == own_robot or peer.get('map_id') != map_id or
                peer.get('map_version') != map_version or
                type(peer.get('observed_at')) not in (int, float) or
                not 0 <= current - peer['observed_at'] <= max_age_s):
            continue
        fresh.append(peer)
    if not fresh:
        return original_choice
    scores = {}
    for exit_id in allowed:
        occupancy = sum(peer.get('current_section') == exit_id for peer in fresh)
        collision = sum(peer.get('current_section') == own_section and
                        peer.get('next_section') == exit_id and
                        peer.get('robot', '') < own_robot for peer in fresh)
        recently_visited = sum(exit_id in peer.get('recent_sections', ())
                               for peer in fresh if isinstance(peer.get('recent_sections', ()), (list, tuple)))
        scores[exit_id] = (collision, occupancy, recently_visited, exit_id != original_choice)
    return min(allowed, key=lambda exit_id: scores[exit_id])
