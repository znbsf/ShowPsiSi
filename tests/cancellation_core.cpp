// Test-only executable. Never compile these environment-controlled gates into
// showpsisi-core; CMake builds this separate target only with an explicit opt-in.
#define SHOWPSISI_TESTING
#include "../core/main.cpp"
#include <cstdlib>

static int runTestCore(int argc,char**argv) {
    const char* gate=std::getenv("SHOWPSISI_TEST_GATE");
    if(gate&&*gate){
        const fs::path prefix=pathFromUtf8(gate);
        const char* configuredStage=std::getenv("SHOWPSISI_TEST_STAGE");
        const std::string stage=configuredStage?configuredStage:"after_progress";
        const char* configuredNumber=std::getenv("SHOWPSISI_TEST_ANALYSIS_NUMBER");
        const unsigned number=configuredNumber?unsigned(std::stoul(configuredNumber)):1;
        const bool fail=std::getenv("SHOWPSISI_TEST_FAIL_AT_GATE")!=nullptr;
        unsigned analysis=0;bool used=false;
        testCheckpoint=[&,stage,number,fail](const char* checkpoint,const std::shared_ptr<AnalysisControl>& control){
            if(std::string(checkpoint)=="before_analysis")++analysis;
            if(used||analysis!=number||stage!=checkpoint)return;
            used=true;
            fs::path ready=prefix,release=prefix;ready += ".ready";release += ".release";
            // Existence is the checkpoint contract: never expose a partially
            // written JSON document to a consumer watching the final path.
            fs::path temporary=ready;temporary += ".tmp";
            const std::string payload=J({{"stage",stage},{"analysis_number",analysis}}).dump()+"\n";
            try {
                std::ofstream out(temporary,std::ios::binary|std::ios::trunc);
                if(!out)throw std::runtime_error("Test gate ready-file open failed");
                out.put(payload.front());out.flush();
                if(!out)throw std::runtime_error("Test gate ready-file write failed");
                // Test-only deterministic seam: hold an incomplete private file
                // until the test explicitly permits publication. No timed race.
                if(std::getenv("SHOWPSISI_TEST_PAUSE_GATE_PUBLICATION")){
                    fs::path publish=prefix;publish += ".publish-release";
                    const auto began=Clock::now();
                    while(!fs::exists(publish)){
                        if(ms(began)>30000)throw std::runtime_error("Test gate publication timed out");
                        std::this_thread::sleep_for(std::chrono::milliseconds(2));
                    }
                }
                out.write(payload.data()+1,std::streamsize(payload.size()-1));
                out.close();
                if(!out)throw std::runtime_error("Test gate ready-file close failed");
                fs::rename(temporary,ready);
            } catch(...) {
                std::error_code ignored;
                fs::remove(temporary,ignored);
                throw;
            }
            const auto began=Clock::now();
            while(!fs::exists(release)&&!(control&&control->cancelled.load())){
                if(ms(began)>30000)throw std::runtime_error("Test gate timed out after 30 seconds");
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            if(fail)throw std::runtime_error("Injected test-only analysis failure");
        };
        // The callback references the variables above, whose lifetime encloses
        // the complete owner loop and its joined input reader.
        return runCore(argc,argv);
    }
    return runCore(argc,argv);
}

#ifdef _WIN32
int wmain(int argc,wchar_t** argv) { return runWide(argc,argv,runTestCore); }
#else
int main(int argc,char** argv) { return runTestCore(argc,argv); }
#endif
