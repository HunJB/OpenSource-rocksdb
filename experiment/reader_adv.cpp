// 기존 (index,bloom 블럭 등 히트도 히트율에 포함)과 다르게 오로지 순수 데이터블럭에 히트한 경우에만 히트율로 계산하여 출력.
// 결과 약 0.1~1% 감소한 형태(디폴트, index사이즈 의도적으로 크게 늘릴경우 큰 차이 가능) 

#include <iostream>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>
#include <memory>
#include "rocksdb/db.h"
#include "rocksdb/table.h"
#include "rocksdb/statistics.h"
#include "workload_gen.h"

using namespace ROCKSDB_NAMESPACE;

const int NUM_REQUESTS = 50000;
const char* DB_PATH = "/tmp/rocksdb_exp_db";

struct AdvResult {
    uint64_t hit, miss; // 순수 데이터 블록 통계
    uint64_t idx_hit;   // 인덱스 히트 (참고용)
    double rate() const { return (hit + miss == 0) ? 0.0 : 100.0 * hit / (hit + miss); }
};

AdvResult measure_adv(size_t mb, const std::vector<int>& keys) {
    BlockBasedTableOptions topt;
    topt.block_cache = NewLRUCache(mb * 1024 * 1024);
    topt.cache_index_and_filter_blocks = true;
    topt.pin_l0_filter_and_index_blocks_in_cache = true;

    Options opt;
    opt.table_factory.reset(NewBlockBasedTableFactory(topt));
    opt.statistics = CreateDBStatistics();

    std::unique_ptr<DB> db;
    DB::Open(opt, DB_PATH, &db);
    
    ReadOptions ro;
    std::string val;
    for (int kid : keys) {
        char key[32];
        snprintf(key, sizeof(key), "key_%07d", kid);
        db->Get(ro, key, &val);
    }

    auto* st = db->GetOptions().statistics.get();
    return {
        st->getTickerCount(BLOCK_CACHE_DATA_HIT), 
        st->getTickerCount(BLOCK_CACHE_DATA_MISS),
        st->getTickerCount(BLOCK_CACHE_INDEX_HIT)
    };
}

int main() {
    system("mkdir -p ./results");
    WorkloadGenerator gen(100000);

    std::vector<std::pair<std::string, std::vector<int>>> workloads = {
        {"Gaussian_s10", gen.gaussian(NUM_REQUESTS, 0.5, 0.10)},
        {"Gaussian_s05", gen.gaussian(NUM_REQUESTS, 0.5, 0.05)},
        {"Zipfian_a10",  gen.zipfian(NUM_REQUESTS,  1.0)},
        {"Zipfian_a05",  gen.zipfian(NUM_REQUESTS,  0.5)},
        {"Hotspot_8020", gen.hotspot(NUM_REQUESTS,  0.20, 0.80)},
        {"Hotspot_9505", gen.hotspot(NUM_REQUESTS,  0.05, 0.95)},
    };

    // 실험 1: 분포별 (32MB 고정)
    std::ofstream csv1("./results/custom_adv_dist.csv");
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
    std::ofstream csv2("./results/custom_adv_cache_sweep.csv");
    csv2 << "workload,cache_mb,hit,miss,hit_rate\n";

    std::cout << "\n[실험 2] 캐시 크기별 순수 데이터 Hit Rate (모든 분포)\n";
    std::cout << std::string(65, '=') << "\n";

    for (auto& [name, keys] : workloads) {
        std::cout << "\n  [" << name << "]\n";
        for (int mb : {4, 8, 16, 32, 64, 128, 256}) {
            AdvResult r = measure_adv(mb, keys);
            std::cout << "    Cache " << std::setw(4) << mb 
                      << " MB → Pure_Data_Rate: " << std::fixed << std::setprecision(2) << std::setw(6) << r.rate() << "%  "
                      << "(Index Hits: " << r.idx_hit << ")\n";
            csv2 << name << "," << mb << "," << r.hit << "," << r.miss << "," << r.rate() << "\n";
        }
    }
    return 0;
}
