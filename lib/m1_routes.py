"""Advisory route ranking. No driving, stopping or motor permissions here."""
import time


def advise(allowed_exits, own_robot, own_section, peers, original_choice,
           *, map_id, map_version, now=None, max_age_s=3):
    """Suggest a locally allowed exit and flag unresolved peer conflicts.

    This is advisory data. A hold recommendation is not a motor command and
    cannot replace local obstacle detection or a traffic-light decision.
    """
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
        return {'selected_exit': original_choice, 'requires_local_hold': False,
                'reason': 'no_fresh_peer_data'}
    scores = {}
    for exit_id in allowed:
        occupancy = sum(peer.get('current_section') == exit_id for peer in fresh)
        intention = sum(peer.get('next_section') == exit_id for peer in fresh)
        # Opposite traffic on the same edge and a simultaneous entry from
        # the same section both require an explicit local safety decision.
        head_on = sum(peer.get('current_section') == exit_id and
                      peer.get('next_section') == own_section for peer in fresh)
        same_entry = sum(peer.get('current_section') == own_section and
                         peer.get('next_section') == exit_id for peer in fresh)
        conflict = bool(occupancy or intention or head_on or same_entry)
        recently_visited = sum(exit_id in peer.get('recent_sections', ())
                               for peer in fresh if isinstance(peer.get('recent_sections', ()), (list, tuple)))
        scores[exit_id] = (conflict, occupancy, intention, recently_visited,
                           exit_id != original_choice)
    safe = [exit_id for exit_id in allowed if not scores[exit_id][0]]
    if not safe:
        return {'selected_exit': original_choice, 'requires_local_hold': True,
                'reason': 'all_locally_allowed_exits_conflict'}
    selected = min(safe, key=lambda exit_id: scores[exit_id])
    return {'selected_exit': selected, 'requires_local_hold': False,
            'reason': 'peer_aware' if selected != original_choice else 'local_choice_clear'}


def choose(allowed_exits, own_robot, own_section, peers, original_choice,
           *, map_id, map_version, now=None, max_age_s=3):
    """Compatibility helper returning only an already locally allowed exit."""
    return advise(allowed_exits, own_robot, own_section, peers, original_choice,
                  map_id=map_id, map_version=map_version, now=now,
                  max_age_s=max_age_s)['selected_exit']
