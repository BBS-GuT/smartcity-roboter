"""Anzeigeadapter fuer vorhandene Scan-Diagnosen, ohne Freigabeentscheidung.

Die unter scan_lock kopierten Eintraege stammen unveraendert aus LF oder KI.
Raumliche Abdeckung ist bewusst kein Merkmal der Datenannahme.
"""
import lidar


def lidar_status(scans, topics, jetzt_mono, jetzt_ros, *, layout='lf', max_zukunft=0.1):
    """Serialisierbare Kanaldiagnose; keine neue Sensorfusion oder Motorfreigabe."""
    if layout not in ('lf', 'ki'):
        raise ValueError('layout muss lf oder ki sein')
    kanaele = []
    for topic in topics or []:
        eintrag = scans.get(topic)
        kanal = dict(topic=topic, empfang=eintrag is not None,
                     empfang_alter_s=None, aufnahme_alter_s=None,
                     qualitaet_ok=None, zeit_ok=None, ablehnungsgrund=None)
        if eintrag is None:
            kanal['ablehnungsgrund'] = 'noch nie ein Scan'
        else:
            empfang, grund, aufnahme = (eintrag[0], eintrag[2 if layout == 'lf' else 3],
                                       eintrag[3 if layout == 'lf' else 4])
            alter = jetzt_mono - empfang
            zeitgrund = lidar.aufnahme_alter(aufnahme, jetzt_ros, max_zukunft=max_zukunft)
            kanal.update(empfang_alter_s=round(alter, 3),
                         aufnahme_alter_s=round(jetzt_ros - aufnahme, 3) if aufnahme is not None else None,
                         # Callback-Grund umfasst auch Frame/Zeit. Keine genauere Ursache erfinden.
                         qualitaet_ok=None if grund else True, zeit_ok=not bool(zeitgrund),
                         annahmegrund=grund)
            kanal['ablehnungsgrund'] = (f'letzter Scan vor {alter:.1f} s' if not 0 <= alter < 1.0
                                       else grund or zeitgrund)
        kanaele.append(kanal)
    return dict(kanaele=kanaele, daten_ok=bool(kanaele) and all(
        k['ablehnungsgrund'] is None for k in kanaele))
