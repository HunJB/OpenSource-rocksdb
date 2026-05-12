// Index/Filter 블록 제외, 순수 데이터 블록 히트율만 측정
// 결과 약 0.1~1% 감소 (Index 크기를 크게 늘리면 차이 더 커짐)

#include <iostream>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>
#include <memory>
#include <ctime>
#include <sstream>
#include <unistd.h>

#include "rocksdb/db.h"
#include "rocksdb/options.h"
#include "rocksdb/table.h"
#include "rocksdb/cache.h"
#include "rocksdb/statistics.h"
#include "workload_gen.h"

using namespace ROCKSDB_NAMESPACE;

const int   NUM_KEYS     = 100000;
const int   NUM_REQUESTS = 50000;
std::string DB_PATH;

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
    uint64_t hit, miss;
    uint64_t idx_hit;
    double rate() const { return (hit + miss == 0) ? 0.0 : 100.0 * hit / (hit + miss); }
};

AdvResult measure_adv(size_t mb, const std::vector<int>& keys) {
    BlockBasedTableOptions topt;
    topt.block_cache = NewLRUCache(mb * 1024 * 1024);
    topt.cache_index_and_filter_blocks = true;
    topt.pin_l0_filter_and_index_blocks_in_cache = true;

    Options opt;
    opt.table_factory.reset(NewBlockBasedTableFactory(topt));
    opt.statistics        = CreateDBStatistics();
    opt.create_if_missing = false;

    std::unique_ptr<DB> db;
    Status s = DB::Open(opt, DB_PATH, &db);
    if (!s.ok()) {
        std::cerr << "DB Open 실패: " << s.ToString() << "\n";
        return {0, 0, 0};
    }

    db->GetOptions().statistics->Reset();

    ReadOptions ro;
    ro.fill_cache = true;
    std::string val;
    for (int kid : keys)
        db->Get(ro, make_key(kid), &val);

    auto* st = db->GetOptions().statistics.get();
    return {
        st->getTickerCount(BLOCK_CACHE_DATA_HIT),
        st->getTickerCount(BLOCK_CACHE_DATA_MISS),
        st->getTickerCount(BLOCK_CACHE_INDEX_HIT)
    };
}

int main() {
    // DB 경로: reader와 같은 슬롯 DB를 공유 (READER_DB_PATH 환경변수)
    const char* env_path = std::getenv("READER_DB_PATH");
    DB_PATH = env_path ? env_path : "/tmp/rocksdb_exp_db";

    // 실험 ID: reader와 같은 폴더에 adv 결과 저장 (READER_RUN_ID 환경변수)
    const char* env_id = std::getenv("READER_RUN_ID");
    std::string run_id = env_id ? env_id
                                : get_timestamp() + "_" + std::to_string(getpid());
    std::string run_dir = "./results/exp_data/run_" + run_id;

    system(("mkdir -p " + run_dir).c_str());

    std::cout << "\n실험 시작 (adv): " << run_id << "\n";
    std::cout << "DB 경로: " << DB_PATH << "\n";

    unsigned seed = (unsigned)std::time(nullptr) ^ (unsigned)getpid();
    WorkloadGenerator gen(NUM_KEYS, seed);
    auto workloads = gen.get_all_workloads(NUM_REQUESTS);

    // 실험 1: 분포별 (32MB 고정)
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

    // 실험 2: 캐시 크기별 Sweep
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
                      << " MB → Pure_Data_Rate: " << std::fixed << std::setprecision(2)
                      << std::setw(6) << r.rate() << "%  "
                      << "(Index Hits: " << r.idx_hit << ")\n";
            csv2 << name << "," << mb << "," << r.hit << "," << r.miss << "," << r.rate() << "\n";
        }
    }

    // 최신 adv 실험 ID 기록 (plot_adv.py 참고용)
    std::ofstream latest("./results/exp_data/latest_adv_run.txt");
    latest << run_id << "\n";

    std::cout << "\n✓ " << csv1_path << "\n";
    std::cout << "✓ " << csv2_path << "\n";

    return 0;
}
