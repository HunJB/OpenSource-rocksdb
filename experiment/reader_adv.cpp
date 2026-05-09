// 기존 (index,bloom 블럭 등 히트도 히트율에 포함)과 다르게 오로지 순수 데이터블럭에 히트한 경우에만 히트율로 계산하여 출력.
// 결과 약 0.1~1% 감소한 형태 가능 (디폴트, index사이즈 의도적으로 크게 늘릴경우 큰 차이 가능하나 권장x)  

#include <iostream>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>
#include <memory>
#include <ctime>
#include <sstream>

#include "rocksdb/db.h"
#include "rocksdb/options.h"
#include "rocksdb/table.h"
#include "rocksdb/cache.h"
#include "rocksdb/statistics.h"
#include "workload_gen.h"

using namespace ROCKSDB_NAMESPACE;

const int   NUM_KEYS     = 100000;
const int   NUM_REQUESTS = 50000;
const char* DB_PATH      = "/tmp/rocksdb_exp_db";

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

struct AdvResult {
    uint64_t hit, miss; // 순수 데이터 블록 통계
    uint64_t idx_hit;   // 인덱스 히트 (참고용)
    double rate() const { 
        return (hit + miss == 0) ? 0.0 : 100.0 * hit / (hit + miss); 
    }
};

AdvResult measure_adv(size_t mb, const std::vector<int>& keys) {
    BlockBasedTableOptions topt;
    topt.block_cache = NewLRUCache(mb * 1024 * 1024);
    // Adv 핵심 설정: 인덱스/필터를 캐시에 강제로 올리고 고정
    topt.cache_index_and_filter_blocks = true;
    topt.pin_l0_filter_and_index_blocks_in_cache = true;

    Options opt;
    opt.table_factory.reset(NewBlockBasedTableFactory(topt));
    opt.statistics = CreateDBStatistics();
    opt.create_if_missing = false;

    std::unique_ptr<DB> db;
    Status s = DB::Open(opt, DB_PATH, &db);
    if (!s.ok()) return {0, 0, 0};
    
    ReadOptions ro;
    ro.fill_cache = true;
    std::string val;
    for (int kid : keys) {
        db->Get(ro, make_key(kid), &val);
    }

    auto* st = db->GetOptions().statistics.get();
    return {
        st->getTickerCount(BLOCK_CACHE_DATA_HIT), 
        st->getTickerCount(BLOCK_CACHE_DATA_MISS),
        st->getTickerCount(BLOCK_CACHE_INDEX_HIT)
    };
}

int main(int argc, char** argv) {
    // ── 타임스탬프 결정: 명령행 인자가 있으면(쉘에서 전달 시) 그것을 사용 ──
    std::string ts;
    if (argc > 1) {
        ts = argv[1];
    } else {
        ts = get_timestamp();
    }

    std::string run_dir = "./results/exp_data/run_" + ts;
    std::string graph_dir = "./results/graph/run_" + ts;

    // ── 실험별 폴더 생성 ──────────────────────────────────
    if (system(("mkdir -p " + run_dir).c_str())) {}
    if (system(("mkdir -p " + graph_dir).c_str())) {}

    std::cout << "\nAdvanced 실험 시작: " << ts << "\n";
    std::cout << "데이터 폴더: " << run_dir << "\n";

    unsigned seed = (unsigned)std::time(nullptr);
    std::cout << "랜덤 시드: " << seed << "\n";

    WorkloadGenerator gen(NUM_KEYS, seed);
    auto workloads = gen.get_all_workloads(NUM_REQUESTS);
    std::cout << "총 " << workloads.size() << "개 분포 실험 예정\n";

    // ── 실험 1: 분포별 순수 데이터 Hit Rate (32MB 고정) ─────
    std::string csv1_path = run_dir + "/custom_adv_dist.csv";
    std::ofstream csv1(csv1_path);
    csv1 << "workload,cache_mb,hit,miss,hit_rate\n";
    
    std::cout << "\n[실험 1] 분포별 순수 데이터 Hit Rate (Cache=32MB)\n";
    std::cout << std::string(65, '=') << "\n";

    for (auto& [name, keys] : workloads) {
        AdvResult r = measure_adv(32, keys);
        std::cout << std::left << std::setw(18) << name
                  << " Hit="  << std::setw(8) << r.hit
                  << " Miss=" << std::setw(8) << r.miss
                  << " Rate=" << std::fixed << std::setprecision(2) << r.rate() << "%\n";
        csv1 << name << ",32," << r.hit << "," << r.miss << "," << r.rate() << "\n";
    }

    // ── 실험 2: 캐시 크기별 Sweep ─────────────────────────
    std::string csv2_path = run_dir + "/custom_adv_cache_sweep.csv";
    std::ofstream csv2(csv2_path);
    csv2 << "workload,cache_mb,hit,miss,hit_rate\n";

    std::cout << "\n[실험 2] 캐시 크기별 순수 데이터 Hit Rate (모든 분포)\n";
    std::cout << std::string(65, '=') << "\n";

    for (auto& [name, keys] : workloads) {
        std::cout << "\n  [" << name << "]\n";
        for (int mb : {4, 8, 16, 32, 64, 128, 256}) {
            AdvResult r = measure_adv(mb, keys);
            std::cout << "    Cache " << std::setw(4) << mb 
                      << " MB → Pure_Rate: " << std::fixed << std::setprecision(2) << r.rate() << "%  "
                      << "(IdxHit: " << r.idx_hit << ")\n";
            csv2 << name << "," << mb << "," << r.hit << "," << r.miss << "," << r.rate() << "\n";
        }
    }

    // ── 메타정보 저장 ─────────────────────────────────────
    std::ofstream meta(run_dir + "/meta_adv.txt");
    meta << "timestamp  : " << ts   << "\n"
         << "seed       : " << seed << "\n"
         << "mode       : Advanced (Pure Data Block Only)\n"
         << "num_keys   : " << NUM_KEYS     << "\n"
         << "num_req    : " << NUM_REQUESTS << "\n";

    // ── 최신 실험 폴더 기록 (plot.py가 참고) ──────────────────
    std::ofstream latest("./results/exp_data/latest_run.txt");
    latest << ts << "\n";

    std::cout << "\n✓ " << csv1_path << "\n";
    std::cout << "✓ " << csv2_path << "\n";

    return 0; 
}
