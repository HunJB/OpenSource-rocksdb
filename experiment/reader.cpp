// 실험 명령어: make clean && make && ./writer && ./reader && ./run_bench.sh && python3 plot.py
// 실험 데이터 삭제 : make cleanall
// 수정 : 실험결과를 같은위치에 생성시키기 위한 타임스탬프 인자만 수정

#include <iostream>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>
#include <memory>
#include <ctime>
#include <sstream>
#include <cstdlib>
#include <unistd.h>

#include "rocksdb/db.h"
#include "rocksdb/options.h"
#include "rocksdb/table.h"
#include "rocksdb/cache.h"
#include "rocksdb/statistics.h"
#include "workload_gen.h"

using namespace ROCKSDB_NAMESPACE;

const int NUM_KEYS     = 100000;
const int NUM_REQUESTS = 50000;

// 병렬 실행 시 run_experiments.sh가 READER_DB_PATH를 슬롯별로 지정
// 미설정 시 기본 경로 사용
std::string DB_PATH;

// ── 타임스탬프 생성 (인자가 없을 경우를 대비한 기본 함수) ────────────────────────
std::string get_timestamp() {
    std::time_t t = std::time(nullptr);
    std::tm* tm   = std::localtime(&t);
    std::ostringstream oss;
    oss << std::put_time(tm, "%Y%m%d_%H%M%S");
    return oss.str();
}

std::string make_key(int id) {
    char buf[32];
    snprintf(buf, sizeof(buf), "key_%07d", id);
    return buf;
}

std::unique_ptr<DB> open_db(size_t cache_bytes) {
    BlockBasedTableOptions topt;
    topt.block_cache = NewLRUCache(cache_bytes);

    Options opt;
    opt.table_factory.reset(NewBlockBasedTableFactory(topt));
    opt.statistics        = CreateDBStatistics();
    opt.create_if_missing = false;

    std::unique_ptr<DB> db;
    Status s = DB::Open(opt, DB_PATH, &db);
    if (!s.ok()) {
        std::cerr << "DB Open 실패: " << s.ToString() << "\n";
        return nullptr;
    }
    return db;
}

struct CacheResult {
    uint64_t hit, miss;
    double rate() const {
        return (hit+miss==0) ? 0.0 : 100.0*hit/(hit+miss);
    }
};

CacheResult measure(size_t cache_bytes, const std::vector<int>& keys) {
    auto db = open_db(cache_bytes);
    if (!db) return {0, 0};

    db->GetOptions().statistics->Reset();
    ReadOptions ro;
    ro.fill_cache = true;
    std::string val;
    for (int kid : keys) db->Get(ro, make_key(kid), &val);

    auto* st = db->GetOptions().statistics.get();
    return {
        st->getTickerCount(BLOCK_CACHE_HIT),
        st->getTickerCount(BLOCK_CACHE_MISS)
    };
}

int main() {
    // DB 경로: READER_DB_PATH 환경변수(병렬 슬롯용), 미설정 시 기본 경로
    const char* env_path = std::getenv("READER_DB_PATH");
    DB_PATH = env_path ? env_path : "/tmp/rocksdb_exp_db";

    // 실험 ID: READER_RUN_ID 환경변수(reader_adv와 같은 폴더 공유용),
    //          미설정 시 타임스탬프+PID로 병렬 충돌 방지
    const char* env_id = std::getenv("READER_RUN_ID");
    std::string run_id = env_id ? env_id
                                : get_timestamp() + "_" + std::to_string(getpid());
    std::string run_dir = "./results/exp_data/run_" + run_id;

    system(("mkdir -p " + run_dir).c_str());

    std::cout << "\n실험 시작: " << run_id << "\n";
    std::cout << "DB 경로: " << DB_PATH << "\n";

    // PID를 XOR하여 같은 초에 시작하는 병렬 runner들도 서로 다른 시드 사용
    unsigned seed = (unsigned)std::time(nullptr) ^ (unsigned)getpid();
    std::cout << "랜덤 시드: " << seed << "\n";

    WorkloadGenerator gen(NUM_KEYS, seed);
    auto workloads = gen.get_all_workloads(NUM_REQUESTS);
    std::cout << "총 " << workloads.size() << "개 분포 실험 예정\n";

    // ── CSV 파일 준비 ──────────────────────────────────────
    std::ofstream csv1(run_dir + "/custom_dist.csv");
    csv1 << "workload,cache_mb,hit,miss,hit_rate\n";

    std::ofstream csv2(run_dir + "/custom_cache_sweep.csv");
    csv2 << "workload,cache_mb,hit,miss,hit_rate\n";

    // ── Sweep 실험 (Exp1·Exp2 통합) ───────────────────────
    // Exp1(분포별 32MB)을 별도 루프 없이 Sweep에서 발췌하여
    // DB Open 횟수를 48 → 42로 절감
    std::cout << "\n[실험] 분포별 × 캐시 크기별 Hit Rate\n";
    std::cout << std::string(55, '=') << "\n";

    std::vector<std::pair<std::string, CacheResult>> dist32_results;

    for (auto& [name, keys] : workloads) {
        std::cout << "\n  [" << name << "]\n";
        for (int mb : {4, 8, 16, 32, 64, 128, 256}) {
            CacheResult r = measure((size_t)mb * 1024 * 1024, keys);
            std::cout << "    Cache " << std::setw(4) << mb
                      << " MB → " << std::fixed << std::setprecision(2)
                      << r.rate() << "%\n";
            csv2 << name << "," << mb << "," << r.hit << ","
                 << r.miss << "," << r.rate() << "\n";

            if (mb == 32) dist32_results.emplace_back(name, r);
        }
    }

    // 32MB 결과를 Exp1 CSV에 저장 (Sweep에서 발췌)
    std::cout << "\n[분포별 Hit Rate 요약 (Cache=32MB)]\n";
    std::cout << std::string(55, '=') << "\n";
    for (auto& [name, r] : dist32_results) {
        std::cout << std::left  << std::setw(18) << name
                  << " Hit="   << std::setw(8)  << r.hit
                  << " Miss="  << std::setw(8)  << r.miss
                  << " Rate="  << std::fixed << std::setprecision(2)
                  << r.rate()  << "%\n";
        csv1 << name << ",32," << r.hit << "," << r.miss << ","
             << r.rate() << "\n";
    }

    // ── 메타정보 저장 ─────────────────────────────────────
    std::ofstream meta(run_dir + "/meta.txt");
    meta << "timestamp  : " << run_id  << "\n"
         << "seed       : " << seed    << "\n"
         << "num_keys   : " << NUM_KEYS     << "\n"
         << "num_req    : " << NUM_REQUESTS << "\n"
         << "db_path    : " << DB_PATH      << "\n";

    // ── 최신 실험 폴더 기록 ───────────────────────────────
    std::ofstream latest("./results/exp_data/latest_run.txt");
    latest << run_id << "\n";

    std::cout << "\n✓ " << run_dir << "/custom_dist.csv\n";
    std::cout << "✓ " << run_dir << "/custom_cache_sweep.csv\n";

    return 0;
}
