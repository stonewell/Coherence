# Licensed under the MIT license
# http://opensource.org/licenses/mit-license.php

# Copyright 2006, Frank Scholz <coherence@beebits.net>

from twisted.internet import task
from twisted.internet import reactor
from twisted.web import xmlrpc, resource, static

from elementtree.ElementTree import Element, SubElement, ElementTree, tostring

from connection_manager_server import ConnectionManagerServer
from rendering_control_server import RenderingControlServer
from av_transport_server import AVTransportServer

class MRRoot(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        
    def childFactory(self, ctx, name):
        ch = super(WebUI, self).childFactory(ctx, name)
        if ch is None:
            p = util.sibpath(__file__, name)
            if os.path.exists(p):
                ch = static.File(p)
        return ch
        
    def listchilds(self, uri):
        cl = ''
        for c in self.children:
                cl += '<li><a href=%s/%s>%s</a></li>' % (uri,c,c)
        return cl

    def render(self,request):
        return '<html><p>root of the MediaRenderer</p><p><ul>%s</ul></p></html>'% self.listchilds(request.uri)


class RootDeviceXML(static.Data):

    def __init__(self, hostname, uuid, urlbase,
                        device_type="urn:schemas-upnp-org:device:MediaRenderer:2",
                        friendly_name='Coherence UPnP A/V MediaRenderer',
                        services=[],
                        devices=[]):
        uuid = str(uuid)
        root = Element('root')
        root.attrib['xmlns']='urn:schemas-upnp-org:device-1-0'
        e = SubElement(root, 'specVersion')
        SubElement( e, 'major').text = '1'
        SubElement( e, 'minor').text = '0'

        SubElement(root, 'URLBase').text = urlbase

        d = SubElement(root, 'device')
        SubElement( d, 'deviceType').text = device_type
        SubElement( d, 'friendlyName').text = friendly_name
        SubElement( d, 'manufacturer').text = ''
        SubElement( d, 'manufacturerURL').text = ''
        SubElement( d, 'modelDescription').text = ''
        SubElement( d, 'modelName').text = ''
        SubElement( d, 'modelNumber').text = ''
        SubElement( d, 'modelURL').text = ''
        SubElement( d, 'serialNumber').text = ''
        SubElement( d, 'UDN').text = uuid
        SubElement( d, 'UPC').text = ''
        SubElement( d, 'presentationURL').text = ''

        if len(services):
            e = SubElement( d, 'serviceList')
            for service in services:
                id = service.get_id()
                s = SubElement( e, 'service')
                SubElement( s, 'serviceType').text = service.get_type()
                SubElement( s, 'serviceId').text = id
                SubElement( s, 'SCPDURL').text = '/' + uuid + '/' + id + '/' + service.scpd_url
                SubElement( s, 'controlURL').text = '/' + uuid + '/' + id + '/' + service.control_url
                SubElement( s, 'eventSubURL').text = '/' + uuid + '/' + id + '/' + service.subscription_url

        if len(services):
            e = SubElement( d, 'deviceList')

        #indent( root, 0)
        self.xml = tostring( root, encoding='utf-8')
        static.Data.__init__(self, self.xml, 'text/xml')
        
class MediaRenderer:

    def __init__(self, coherence):
        from uuid import UUID
        self.coherence = coherence
        self.uuid = UUID()
        self._services = []
        self._devices = []
        
        self.connection_manager_server = ConnectionManagerServer(None)
        self._services.append(self.connection_manager_server)

        self.rendering_control_server = RenderingControlServer(None)
        self._services.append(self.rendering_control_server)

        self.av_transport_server = AVTransportServer(None)
        self._services.append(self.av_transport_server)

        self.web_resource = MRRoot()
        self.coherence.add_web_resource( str(self.uuid), self.web_resource)
        self.web_resource.putChild( 'description.xml',
                                RootDeviceXML( self.coherence.hostname,
                                str(self.uuid),
                                self.coherence.urlbase,
                                services=self._services,
                                devices=self._devices))

        self.web_resource.putChild('ConnectionManager', self.connection_manager_server)
        self.web_resource.putChild('RenderingControl', self.rendering_control_server)
        self.web_resource.putChild('AVTransport', self.av_transport_server)


        self.register()

        
    def register(self):
        s = self.coherence.ssdp_server
        uuid = str(self.uuid)
        print 'MediaRenderer register'
        # we need to do this after the children are there, since we send notifies
        s.register('local',
                    '%s::upnp:rootdevice' % uuid,
                    'upnp:rootdevice',
                    self.coherence.urlbase + uuid + '/' + 'description.xml')

        s.register('local',
                    uuid,
                    uuid,
                    self.coherence.urlbase + uuid + '/' + 'description.xml')

        s.register('local',
                    '%s::urn:schemas-upnp-org:device:MediaRenderer:2' % uuid,
                    'urn:schemas-upnp-org:device:MediaRenderer:2',
                    self.coherence.urlbase + uuid + '/' + 'description.xml')

        for service in self._services:
            s.register('local',
                        '%s::%s' % (uuid,service.get_type()),
                        service.get_type(),
                        self.coherence.urlbase + uuid + '/' + service.id + '/' + 'scpd.xml')     