#pragma once
// A pinned external decoder receives only bounded elementary bytes over stdin.
// No shell, network URL or user-provided command arguments are used.
namespace mediadecode {
struct ProcessResult{Bytes bytes;std::string error;unsigned exitCode=0;uint64_t pid=0;bool cancelled=false,timedOut=false,overflow=false;};
#ifdef _WIN32
struct Handle {
 HANDLE h=nullptr;Handle()=default;explicit Handle(HANDLE value):h(value){};Handle(const Handle&)=delete;Handle& operator=(const Handle&)=delete;
 ~Handle(){close();}void close(){if(h&&h!=INVALID_HANDLE_VALUE)CloseHandle(h);h=nullptr;}
};
inline std::wstring quote(const std::wstring& arg){std::wstring out=L"\"";size_t slashes=0;for(auto c:arg){if(c==L'\\'){++slashes;continue;}if(c==L'"')out.append(slashes*2+1,L'\\');else out.append(slashes,L'\\');slashes=0;out+=c;}out.append(slashes*2,L'\\');out+=L'"';return out;}
inline ProcessResult run(const fs::path& executable,const std::vector<std::string>& args,const Bytes& input,const std::atomic<bool>* cancel,const std::function<void(uint64_t)>& started={}){
 ProcessResult result;if(cancel&&cancel->load()){result.cancelled=true;return result;}
 Handle inRead,inWrite,outRead,outWrite,errRead,errWrite;SECURITY_ATTRIBUTES security{sizeof(SECURITY_ATTRIBUTES),nullptr,TRUE};
 if(!CreatePipe(&inRead.h,&inWrite.h,&security,0)||!CreatePipe(&outRead.h,&outWrite.h,&security,0)||!CreatePipe(&errRead.h,&errWrite.h,&security,0)){result.error="Cannot create decoder pipes";return result;}
 SetHandleInformation(inWrite.h,HANDLE_FLAG_INHERIT,0);SetHandleInformation(outRead.h,HANDLE_FLAG_INHERIT,0);SetHandleInformation(errRead.h,HANDLE_FLAG_INHERIT,0);
 SIZE_T size=0;InitializeProcThreadAttributeList(nullptr,1,0,&size);std::vector<uint8_t> attributes(size);auto* list=reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(attributes.data());
 if(!InitializeProcThreadAttributeList(list,1,0,&size)){result.error="Cannot initialize decoder handle isolation";return result;}
 HANDLE inherited[]={inRead.h,outWrite.h,errWrite.h};const bool updated=UpdateProcThreadAttribute(list,0,PROC_THREAD_ATTRIBUTE_HANDLE_LIST,inherited,sizeof(inherited),nullptr,nullptr)!=FALSE;
 STARTUPINFOEXW startup{};startup.StartupInfo.cb=sizeof(startup);startup.StartupInfo.dwFlags=STARTF_USESTDHANDLES;startup.StartupInfo.hStdInput=inRead.h;startup.StartupInfo.hStdOutput=outWrite.h;startup.StartupInfo.hStdError=errWrite.h;startup.lpAttributeList=list;
 std::wstring command=quote(executable.native());for(const auto& arg:args)command+=L" "+quote(pathFromUtf8(arg).native());PROCESS_INFORMATION process{};
 const bool launched=updated&&CreateProcessW(executable.c_str(),command.data(),nullptr,nullptr,TRUE,CREATE_NO_WINDOW|CREATE_SUSPENDED|EXTENDED_STARTUPINFO_PRESENT,nullptr,nullptr,&startup.StartupInfo,&process)!=FALSE;DeleteProcThreadAttributeList(list);
 if(!launched){result.error="Cannot start isolated decoder (Windows error "+std::to_string(GetLastError())+")";return result;}
 Handle child(process.hProcess),thread(process.hThread),job(CreateJobObjectW(nullptr,nullptr));JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE|JOB_OBJECT_LIMIT_ACTIVE_PROCESS|JOB_OBJECT_LIMIT_PROCESS_MEMORY;limits.BasicLimitInformation.ActiveProcessLimit=1;limits.ProcessMemoryLimit=384*1024*1024;
 if(!job.h||!SetInformationJobObject(job.h,JobObjectExtendedLimitInformation,&limits,sizeof(limits))||!AssignProcessToJobObject(job.h,child.h)){TerminateProcess(child.h,1);WaitForSingleObject(child.h,1000);result.error="Cannot enforce decoder process/memory ownership";return result;}
 inRead.close();outWrite.close();errWrite.close();std::atomic<bool> overflow{false},failed{false};std::string stderrText;std::thread writer,stdoutReader,stderrReader;
 try{
  stdoutReader=std::thread([&](){try{uint8_t chunk[16384];DWORD n=0;while(ReadFile(outRead.h,chunk,sizeof(chunk),&n,nullptr)&&n){if(result.bytes.size()+n>4*1024*1024){overflow=true;TerminateJobObject(job.h,1);break;}result.bytes.insert(result.bytes.end(),chunk,chunk+n);}}catch(...){failed=true;TerminateJobObject(job.h,1);}});
  stderrReader=std::thread([&](){try{char chunk[4096];DWORD n=0;while(ReadFile(errRead.h,chunk,sizeof(chunk),&n,nullptr)&&n)if(stderrText.size()<65536)stderrText.append(chunk,std::min<size_t>(n,65536-stderrText.size()));}catch(...){failed=true;TerminateJobObject(job.h,1);}});
  writer=std::thread([&](){size_t offset=0;while(offset<input.size()){DWORD n=0;if(!WriteFile(inWrite.h,input.data()+offset,DWORD(std::min<size_t>(65536,input.size()-offset)),&n,nullptr)||!n)break;offset+=n;}inWrite.close();});
  result.pid=process.dwProcessId;ResumeThread(thread.h);if(started)started(result.pid);const auto deadline=Clock::now()+std::chrono::seconds(8);while(WaitForSingleObject(child.h,25)==WAIT_TIMEOUT){if(cancel&&cancel->load()){result.cancelled=true;TerminateJobObject(job.h,1);break;}if(Clock::now()>=deadline){result.timedOut=true;TerminateJobObject(job.h,1);break;}}
 }catch(...){failed=true;TerminateJobObject(job.h,1);}
 if(WaitForSingleObject(child.h,1000)!=WAIT_OBJECT_0){TerminateJobObject(job.h,1);WaitForSingleObject(child.h,1000);}if(writer.joinable())writer.join();if(stdoutReader.joinable())stdoutReader.join();if(stderrReader.joinable())stderrReader.join();DWORD code=1;GetExitCodeProcess(child.h,&code);result.exitCode=code;result.overflow=overflow.load();
 if(result.cancelled)result.error="Decoder request cancelled";else if(result.timedOut)result.error="Decoder exceeded the eight-second wall-time bound";else if(result.overflow)result.error="Decoder output exceeded four MiB";else if(failed)result.error="Decoder pipe worker failed";else if(code)result.error="Decoder rejected the collected ES";
 if(!stderrText.empty()){Bytes raw(stderrText.begin(),stderrText.end());result.error+=(result.error.empty()?"":"; ")+carouselcontent::text(raw);}return result;
}
#else
inline ProcessResult run(const fs::path&,const std::vector<std::string>&,const Bytes&,const std::atomic<bool>*,const std::function<void(uint64_t)>& started={}){ProcessResult result;result.error="Pinned decoder execution is currently implemented for Windows only";return result;}
#endif
inline std::string base64(const Bytes& bytes){static const char alphabet[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";std::string result;result.reserve((bytes.size()+2)/3*4);for(size_t p=0;p<bytes.size();p+=3){unsigned v=unsigned(bytes[p])<<16;if(p+1<bytes.size())v|=unsigned(bytes[p+1])<<8;if(p+2<bytes.size())v|=bytes[p+2];result+=alphabet[(v>>18)&63];result+=alphabet[(v>>12)&63];result+=p+1<bytes.size()?alphabet[(v>>6)&63]:'=';result+=p+2<bytes.size()?alphabet[v&63]:'=';}return result;}
inline std::vector<Bytes> pngFrames(const Bytes& bytes){std::vector<Bytes> frames;size_t offset=0;while(offset<bytes.size()){const size_t start=offset;if(bytes.size()-offset<8||hex(bytes.data()+offset,8)!="89504E470D0A1A0A")throw std::runtime_error("Decoder did not produce PNG frames");offset+=8;bool ended=false;while(bytes.size()-offset>=12){uint64_t n=(uint32_t(bytes[offset])<<24)|(uint32_t(bytes[offset+1])<<16)|(uint32_t(bytes[offset+2])<<8)|bytes[offset+3];if(n>bytes.size()-offset-12)throw std::runtime_error("Truncated decoded PNG chunk");const bool end=std::memcmp(bytes.data()+offset+4,"IEND",4)==0;offset+=size_t(n)+12;if(end){ended=true;break;}}if(!ended)throw std::runtime_error("Decoded PNG lacks IEND");frames.emplace_back(bytes.begin()+start,bytes.begin()+offset);if(frames.size()>16)throw std::runtime_error("Decoded frame count exceeds sixteen");}return frames;}
}
