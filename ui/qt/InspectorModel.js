// Presentation only: identities, decoding and repeat counts belong to the engine.
var inspector = {
    shortSyntax: function(r) { return r.versioning_supported === false || r.table_id === 0x70 || r.table_id === 0x73; },
    hex: function(n) { return '0x' + Number(n).toString(16).toUpperCase().padStart(4, '0'); },
    title: function(r) {
        var label = r.name + ' · PID ' + this.hex(r.pid);
        if (this.shortSyntax(r)) label += ' · ' + (r.utc_time || 'time unavailable');
        else label += ' · ' + this.hex(r.extension) + ' · v' + r.version + (r.current ? ' current' : ' next') + ' · §' + r.section + '/' + r.last_section;
        return label + ' · ×' + r.count + (r.valid === false ? ' · INVALID' : '');
    },
    help: function(key) {
        return ({program_number:'Program identifier; 0 refers to network signalling',service_id:'Service identifier; interpret with its transport stream and original network',
            pmt_pid:'Packet identifier carrying this program map',PCR_PID:'Packet identifier carrying the program clock reference',pcr_pid:'Packet identifier carrying the program clock reference',
            elementary_PID:'Packet identifier carrying this elementary stream',elementary_pid:'Packet identifier carrying this elementary stream',
            stream_type:'Signalled elementary stream coding type',UTC_time:'Broadcast UTC time',utc_time:'Broadcast UTC time',
            transport_stream_id:'Transport stream identifier',original_network_id:'Original network identifier',network_id:'Network identifier',bouquet_id:'Bouquet identifier',
            descriptor_tag:'Descriptor type; private tags require their namespace',descriptor_length:'Descriptor payload length in bytes',
            count:'Identical section arrivals, aggregated by the engine',raw:'Original descriptor bytes; unknown semantics remain unknown'})[key] || '';
    },
    node: function(path, label, value) {
        var n={path:path,label:label,fields:[],children:[]};
        if (value && typeof value==='object') Object.keys(value).forEach(function(k){
            var v=value[k];
            if(v!==null && typeof v==='object') {
                var childLabel=Array.isArray(value)?'['+k+']':k;
                if(Array.isArray(value) && path.endsWith('/programs'))childLabel='Program '+v.service_id+' → PMT '+inspector.hex(v.pmt_pid);
                if(Array.isArray(value) && path.endsWith('/streams'))childLabel='Stream PID '+inspector.hex(v.pid)+' · type '+inspector.hex(v.type);
                if(Array.isArray(value) && path.endsWith('/transports'))childLabel='Transport '+inspector.hex(v.transport_stream_id)+' · ONID '+inspector.hex(v.original_network_id);
                n.children.push(inspector.node(path+'/'+k,childLabel,v));
            }
            else n.fields.push({name:k,value:String(v===null?'Not carried':v),help:inspector.help(k)});
        });
        return n;
    },
    native: function(value,path) {
        var a=value.attributes || {}, suffix=['service_id','program_number','elementary_PID','transport_stream_id','bouquet_id'].filter(function(k){return a[k]!==undefined;}).map(function(k){return a[k];}).join(' · ');
        var n=this.node(path,value.name+(suffix?' · '+suffix:''),a);
        (value.children || []).forEach(function(c,i){n.children.push(inspector.native(c,path+'/'+i));});
        if(value.text)n.fields.push({name:'text',value:value.text,help:''});
        return n;
    },
    structure: function(d) {
        if(!d.id)return null;
        var header={table_id:this.hex(d.table_id),pid:this.hex(d.pid),bytes:d.bytes};
        if(!this.shortSyntax(d)){header.table_id_extension=this.hex(d.extension);header.version_number=d.version;header.current_next_indicator=d.current;header.section_number=d.section;header.last_section_number=d.last_section;}
        if(d.utc_time || (d.fields || {}).utc_time)header.utc_time=d.utc_time || d.fields.utc_time;
        var root=this.node('section',d.name+' · selected section',header);
        var native=d.section_native_table;
        if(!native && d.native_table_complete && (d.native_table_sources || []).length===1 && d.native_table_sources[0].id===d.id)native=d.native_table;
        if(native)root.children.push(this.native(native,'section/decoded'));
        else root.children.push(this.node('section/decoded','Decoded fields',d.fields || {}));
        // Raw descriptor loop ownership and offsets come exclusively from the engine.
        if((d.descriptors || []).length){var descriptors={path:'section/descriptors',label:'Descriptors · exact section',fields:[],children:[]};
            d.descriptors.forEach(function(x,i){
                var n=inspector.node('section/descriptors/'+i,(x.name || 'Unknown descriptor')+' · tag '+inspector.hex(x.tag),{descriptor_tag:inspector.hex(x.tag),descriptor_length:x.length,decode_status:x.decode_status || 'unknown',raw:x.raw || ''});
                if(x.native)n.children.push(inspector.native(x.native,n.path+'/decoded'));
                if(Object.keys(x.fields || {}).length)n.children.push(inspector.node(n.path+'/fields','Decoded fields',x.fields));
                // Do not guess offsets for SDK fields or assembled tables.
                if(Number.isInteger(x.offset) && Number.isInteger(x.length))n.range={offset:x.offset,length:x.length+2};
                descriptors.children.push(n);
            });root.children.push(descriptors);
        }
        return root;
    },
    find: function(root,path) {
        if(!root)return null;
        if(root.path===path)return root;
        if(path.indexOf(root.path+'/')!==0)return null;
        for(var i=0;i<(root.children || []).length;i++){
            var match=inspector.find(root.children[i],path);if(match)return match;
        }
        return null;
    },
    flatten: function(root,closed,depth,limits) {
        if(!root)return [];
        var out=[Object.assign({},root,{depth:depth || 0})];
        var children=root.children || [],limit=limits ? (limits[root.path] || 100) : children.length;
        if(!closed[root.path]) {
            children.slice(0,limit).forEach(function(c){out=out.concat(inspector.flatten(c,closed,(depth || 0)+1,limits));});
            if(children.length>limit)out.push({path:root.path+'/more',label:'Load next '+Math.min(100,children.length-limit)+' of '+children.length,fields:[],children:[],more:root.path,depth:(depth || 0)+1});
        }
        return out;
    },
    summary: function(d,state) {
        var f=d.fields || {}, text=[];
        if(d.name==='PAT') (f.programs || []).forEach(function(p){
            var sid=p.service_id===undefined?p.program_number:p.service_id;
            var services=(state.services || []).filter(function(s){return s.id===sid && s.ts_id===d.extension;});
            // TSID + SID may still match multiple ONIDs: never choose an arbitrary name.
            text.push('Program '+sid+' → PMT '+inspector.hex(p.pmt_pid)+(services.length===1?' · '+services[0].name:services.length>1?' · ambiguous service identity':''));
        });
        if(d.name==='PMT')text.push('Program '+d.extension+' · PCR '+(f.pcr_pid!==undefined?this.hex(f.pcr_pid):f.PCR_PID!==undefined?this.hex(f.PCR_PID):'unavailable')+' · '+(f.streams || []).length+' streams');
        if(d.name==='TDT' || d.name==='TOT')text.push('UTC '+(f.utc_time || d.utc_time || 'unavailable')+' · '+(d.name==='TDT'?'No CRC in TDT':'TOT CRC: '+((d.crc || {}).status || 'unavailable')));
        if(d.name==='BAT')text.push('Bouquet '+this.hex(d.extension));
        if(d.name==='NIT')text.push('Network '+this.hex(d.extension));
        if(d.name==='SDT')text.push('Transport stream '+this.hex(d.extension)+' · '+(d.services || []).length+' services');
        return text.slice(0,8).join('\n')+(text.length>8?'\n'+(text.length-8)+' more entries in the structure tree':'');
    }
};
if(typeof module!=='undefined')module.exports=inspector;
