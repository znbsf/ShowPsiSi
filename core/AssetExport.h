// Included in Engine: bounded, source-identified exports. No protocol parsing in UI.
    J exportAsset(const J& args) {
        if(!complete||args.at("analysis_revision")!=revision||!analysisSourceKnown)throw std::runtime_error("Stale or incomplete export analysis_revision");
        auto unchanged=[&](){return fs::is_regular_file(source)&&fs::file_size(source)==totalBytes&&fs::last_write_time(source)==analysisSourceStamp;};
        if(!unchanged())throw std::runtime_error("Source changed since analysis");
        const std::string kind=args.at("kind");Bytes bytes;J evidence=J::object();
        J q=args;q.erase("path");q.erase("kind");
        if(kind=="section"){
            auto found=ids.find(args.at("source_id").get<std::string>());if(found==ids.end())throw std::runtime_error("Unknown section source");const auto& r=records.at(found->second);
            auto cutoff=args.value("at_packet",packets-1);if(cutoff>=packets||r.ends.empty()||r.ends.front()>cutoff)throw std::runtime_error("Section not observed at cutoff");bytes=r.raw;evidence=summary(r,cutoff);evidence["layer"]="original_section_including_CRC_where_present";
        }else if(kind=="packet"||kind=="packet_frame"){
            auto packet=queryPacket({{"analysis_revision",revision},{"packet_index",args.at("packet_index")}});const auto raw=packet.at(kind=="packet"?"raw_hex":"frame_hex").get<std::string>();for(size_t i=0;i<raw.size();i+=2)bytes.push_back(uint8_t(std::stoul(raw.substr(i,2),nullptr,16)));evidence=packet;evidence.erase("raw_hex");evidence.erase("frame_hex");
        }else if(kind=="pes"||kind=="es"){
            bool found=false;auto scan=readPes(q,[&](const mediawire::PesPacket& p,uint64_t first,uint64_t last){if(evidence.value("visited",size_t(0))==args.at("pes_index")){size_t offset=kind=="es"?p.payload_offset:0;bytes.assign(p.raw.begin()+offset,p.raw.end());evidence=pesMetadata(p,args.at("pes_index"),first,last);evidence["source_fragments"]=pesFragments(p,offset,bytes.size());found=true;return false;}evidence["visited"]=evidence.value("visited",size_t(0))+1;return true;});
            if(!found)throw std::runtime_error("Selected complete PES not observed in range");evidence["scan"]=scan;evidence["layer"]=kind=="es"?"collected_ES_payload_of_one_PES_not_codec_frame":"original_PES";
        }else if(kind=="module"||kind=="object"){
            q["limit"]=1;q["offset"]=0;auto checked=queryCarousel(q);if(!checked.contains("module_id")||!checked.contains("biop"))throw std::runtime_error("Incomplete module cannot be exported");
            const uint64_t cutoff=checked.at("at_packet");const auto window=coverage.value("partial",false)?segmentRecords(cutoff):std::vector<Record>{};auto snapshot=dsmccsignalling::reconstruct(duck,coverage.value("partial",false)?window:records,checked.at("pid"),checked.at("download_id"),cutoff);const auto& module=snapshot.modules.at(args.at("module_id").get<unsigned>());
            if(module.status!="complete"||snapshot.status=="resource_limit")throw std::runtime_error("Incomplete module cannot be exported");bytes=carouselcontent::assemble(module);evidence=checked;evidence.erase("content");evidence.erase("module_page");
            if(kind=="object"){
                if(!checked.contains("object"))throw std::runtime_error("Select a validated BIOP object");biopwire::BiopModule parsed;biopwire::decode_biop_module(bytes.data(),bytes.size(),parsed);size_t offset=checked.at("object").at("offset");auto i=std::find(parsed.offsets.begin(),parsed.offsets.end(),offset);if(i==parsed.offsets.end())throw std::runtime_error("Invalid object offset");const auto& object=parsed.objects.at(size_t(i-parsed.offsets.begin()));bytes=object.object_kind==0x66696c00?object.content:object.raw;evidence["layer"]=object.object_kind==0x66696c00?"file_content":"BIOP_object_envelope";
            }else evidence["layer"]="assembled_complete_module_no_decompression";
        }else if(kind=="png"||kind=="wav"){
            if(mediaToken.empty()||args.at("preview_token")!=mediaToken)throw std::runtime_error("Stale decoded preview token");evidence=decodedPreview;evidence.erase("frames");
            if(kind=="png"){if(decodedPreview.value("kind",std::string())!="video")throw std::runtime_error("Not a video preview");size_t i=args.at("frame_index");if(i>=decodedFrames.size())throw std::runtime_error("Frame index out of bounds");bytes=decodedFrames[i];evidence["frame_index"]=i;evidence["layer"]="derived_preview_PNG_not_original_resolution_or_timing";}
            else{if(decodedPreview.value("kind",std::string())!="audio"||decodedPcm.empty())throw std::runtime_error("Not a PCM preview");auto put=[&](uint32_t n,size_t size){for(size_t i=0;i<size;++i)bytes.push_back(uint8_t(n>>(8*i)));};auto tag=[&](const char* t){bytes.insert(bytes.end(),t,t+4);};tag("RIFF");put(36+uint32_t(decodedPcm.size()),4);tag("WAVE");tag("fmt ");put(16,4);put(1,2);put(1,2);put(48000,4);put(96000,4);put(2,2);put(16,2);tag("data");put(uint32_t(decodedPcm.size()),4);bytes.insert(bytes.end(),decodedPcm.begin(),decodedPcm.end());evidence["layer"]="derived_bounded_PCM_preview_WAV_mono_48000_Hz_s16le";}
        }else if(kind=="report"){
            evidence=compactState(args.value("at_packet",UINT64_MAX));evidence["transport_statistics"]=transportStatistics.summary(bitrate);const auto text=evidence.dump(2)+"\n";bytes.assign(text.begin(),text.end());evidence={{"layer","analysis_summary_JSON"},{"scope","Analyzed coverage and metrics; not a complete export of every paged protocol collection"}};
        }else throw std::runtime_error("Unsupported export kind");
        if(!unchanged())throw std::runtime_error("Source changed while preparing output");
        fs::path path=fs::absolute(pathFromUtf8(args.at("path").get<std::string>()));if(fs::exists(path)||fs::exists(manifestPath(path)))throw std::runtime_error("Output or manifest already exists; choose a new path");
        if(!fs::is_directory(path.parent_path()))throw std::runtime_error("Output directory does not exist");
        auto temporary=path;temporary+=pathFromUtf8(".showpsisi-"+std::to_string(Clock::now().time_since_epoch().count())+".tmp");auto temporaryManifest=manifestPath(temporary);
        J receipt={{"path",pathUtf8(path)},{"manifest",pathUtf8(manifestPath(path))},{"kind",kind},{"bytes",bytes.size()},{"sha256",carouselcontent::sha(bytes)},{"source",pathUtf8(source)},{"source_bytes",totalBytes},{"analysis_revision",revision},{"selection",q},{"coverage",coverage},{"evidence",evidence}};
        ExportFile data(temporary);data.write(bytes.data(),bytes.size());data.close();ExportFile manifest(temporaryManifest);const auto text=receipt.dump(2)+"\n";manifest.write(text.data(),text.size());manifest.close();
        // Atomic no-replace publication. Hard links stay on the selected volume.
        // Refuse filesystems lacking this operation instead of promising overwrite.
        if(!unchanged())throw std::runtime_error("Source changed before publishing output");
        fs::create_hard_link(temporary,path);try{fs::create_hard_link(temporaryManifest,manifestPath(path));}catch(...){std::error_code ignored;fs::remove(path,ignored);throw;}
        return {{"path",pathUtf8(path)},{"manifest",pathUtf8(manifestPath(path))},{"kind",kind},{"bytes",bytes.size()},{"sha256",receipt.at("sha256")},{"analysis_revision",revision}};
    }
