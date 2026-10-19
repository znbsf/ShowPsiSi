"""Independently authored DVB-I XML inputs; no third-party sample is bundled.

These tiny documents exercise the bounded local ETSI TS 103 770 V1.2.1
projection. They are not certified full-schema instances or playable services.
All example identifiers and URLs are deliberately non-production. Callers own
writing the returned bytes to isolated temporary files.
"""
from xml.sax.saxutils import escape, quoteattr

PROFILE = 'etsi-ts-103770-v1.2.1'
NAMESPACE = 'urn:dvb:metadata:servicediscovery:2024'
TYPES_NAMESPACE = 'urn:dvb:metadata:servicediscovery-types:2023'
SERVICE_A = 'tag:example.invalid,2026:service:alpha'
SERVICE_B = 'tag:example.invalid,2026:service:beta'


def element(name, text='', *, prefix='', attributes=None):
    """Make one escaped text element; callers explicitly provide XML structure."""
    tag = f'{prefix}:{name}' if prefix else name
    attrs = ''.join(f' {key}={quoteattr(str(value))}' for key, value in (attributes or {}).items())
    return f'<{tag}{attrs}>{escape(str(text))}</{tag}>'


def document(body='', *, namespace=NAMESPACE, prefix='', root='ServiceList', attributes=None):
    tag = f'{prefix}:{root}' if prefix else root
    declaration = f'xmlns:{prefix}' if prefix else 'xmlns'
    attrs = ''.join(f' {key}={quoteattr(str(value))}' for key, value in
                    {'id': 'tag:example.invalid,2026:list:independent', 'xml:lang': 'en', **(attributes or {})}.items())
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<{tag} {declaration}={quoteattr(namespace)} '
            f'xmlns:types={quoteattr(TYPES_NAMESPACE)} '
            f'xmlns:ext="urn:example.invalid:dvbi:extension" version="1"{attrs}>\n'
            f'{body}\n</{tag}>\n').encode('utf-8')


def service(identifier=SERVICE_A, name='Shared programme', *, prefix='', instances='',
            identifier_xml=None, extra=''):
    tag = f'{prefix}:Service' if prefix else 'Service'
    identity = (element('UniqueIdentifier', identifier, prefix=prefix)
                if identifier_xml is None else identifier_xml)
    return (f'<{tag} version="1">{identity}{instances}'
            f'{element("ServiceName", name, prefix=prefix, attributes={"xml:lang": "en"})}'
            f'{element("ProviderName", "Independent fixture", prefix=prefix)}{extra}</{tag}>')


def instance(instance_id='terrestrial', delivery='DVBTDeliveryParameters', *, prefix='',
             triplet=(901, 101, 1), extra='', omit_id=False):
    q = lambda tag: f'{prefix}:{tag}' if prefix else tag
    attrs = '' if omit_id else f' id={quoteattr(instance_id)}'
    if delivery == 'DASHDeliveryParameters':
        body = (f'<{q("UriBasedLocation")} contentType="application/dash+xml">'
                f'{element("URI", "https://media.example.invalid/alpha.mpd", prefix="types")}'
                f'</{q("UriBasedLocation")}>')
    else:
        onid, tsid, sid = triplet
        body = (f'<{q("DVBTriplet")} origNetId={quoteattr(str(onid))} '
                f'tsId={quoteattr(str(tsid))} serviceId={quoteattr(str(sid))}/>')
    return (f'<{q("ServiceInstance")}{attrs} priority="1">'
            f'<{q(delivery)}>{body}</{q(delivery)}>{extra}</{q("ServiceInstance")}>')


def lcn_table(entries=((7, SERVICE_A), (8, SERVICE_B)), *, prefix='', region='north'):
    q = lambda tag: f'{prefix}:{tag}' if prefix else tag
    channels = ''.join(f'<{q("LCN")} channelNumber={quoteattr(str(number))} '
                       f'serviceRef={quoteattr(identifier)}/>' for number, identifier in entries)
    return (f'<{q("LCNTable")}>{element("TargetRegion", region, prefix=prefix)}'
            f'{channels}</{q("LCNTable")}>')


def fixture(*, prefix='', namespace=NAMESPACE):
    """Two same-name services, four distinct deliveries, languages and regions."""
    q = lambda tag: f'{prefix}:{tag}' if prefix else tag
    names = element('ServiceName', '新闻 & <测试> 🎬', prefix=prefix, attributes={'xml:lang': 'zh'})
    alternatives = ''.join(instance(kind, delivery, prefix=prefix) for kind, delivery in (
        ('terrestrial', 'DVBTDeliveryParameters'), ('satellite', 'DVBSDeliveryParameters'),
        ('cable', 'DVBCDeliveryParameters'), ('broadband', 'DASHDeliveryParameters')))
    channels = (f'<{q("LCNTableList")}>'
                f'{lcn_table(prefix=prefix)}'
                f'{lcn_table(((17, SERVICE_A),), prefix=prefix, region="south")}'
                f'</{q("LCNTableList")}>')
    body = (element('Name', 'Independent XML evidence lab', prefix=prefix) +
            element('ProviderName', 'Independent fixture publisher', prefix=prefix) + channels +
            service(prefix=prefix, instances=alternatives, extra=names) +
            service(SERVICE_B, prefix=prefix, instances=instance('fallback', prefix=prefix)) +
            '<ext:FutureFeature ext:flag="preserve &amp; inspect">unknown extension</ext:FutureFeature>')
    return document(body, prefix=prefix, namespace=namespace)


def many_services(count):
    return document(''.join(service(f'tag:example.invalid,2026:service:{number}',
                                   f'Programme {number}') for number in range(count)))


def transport_fixture():
    """Tiny original TS fixture, independent of optional sample downloads."""
    from make_fixture import descriptor, section, word
    name = b'TS session retained'
    desc = descriptor(0x48, b'\x01\x00' + bytes([len(name)]) + name)
    records = [(0, section(0, 101, 1, word(1) + word(0xe100))),
               (0x100, section(2, 1, 1, word(0xe200) + word(0xf000))),
               (0x11, section(0x42, 101, 1, word(901) + b'\xff' +
                              word(1) + b'\xff' + word(0x8000 | len(desc)) + desc))]
    packets = [bytes([0x47, 0x40 | (pid >> 8), pid & 255, 0x10, 0]) + raw +
               b'\xff' * (183 - len(raw)) for pid, raw in records]
    return b''.join(packets + [bytes([0x47, 0x1f, 0xff, 0x10]) + b'\xff' * 184] * 2)
