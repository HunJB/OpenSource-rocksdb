#include <iostream>
#include <fstream>
#include <iomanip>
#include <string>
#include <vector>
#include <memory>

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

std::string make_key(int id) {
    char buf[32];
    snprintf(buf, sizeof(buf), "key_%07d", id);
    return buf;
}

// ── 캐시 크기를 인자로 받아 DB 오픈 ──────────────────────
std::unique_ptr<DB> open_db(size_t cache_bytes) {
    BlockBasedTableOptions topt;
    topt.block_cache = NewLRUCache(cache_bytes); // ← 새 LRU 캐시

    Options opt;
    opt.table_factory.reset(NewBlockBasedTableFactory(topt));
    opt.statistics        = CreateDBStatistics();
    opt.create_if_missing = false; // ← 기존 DB 사용 (writer가 만든 것)

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
        return (hit + miss == 0) ? 0.0 : 100.0 * hit / (hit + miss);
    }
};

// ── Cold Cache 상태에서 읽기 측정 ────────────────────────
CacheResult measure(size_t cache_bytes, const std::vector<int>& keys) {
    // DB를 새로 열 때마다 완전히 새로운 캐시 생성 (Cold Cache 보장)
    auto db = open_db(cache_bytes);
    if (!db) return {0, 0};

    // 통계 초기화
    db->GetOptions().statistics->Reset();

    ReadOptions ro;
    ro.fill_cache = true;
    std::string val;

    for (int kid : keys)
        db->Get(ro, make_key(kid), &val);

    auto* st = db->GetOptions().statistics.get();
    return {
        st->getTickerCount(BLOCK_CACHE_HIT),
        st->getTickerCount(BLOCK_CACHE_MISS)
    };
    // unique_ptr 소멸 → 캐시 해제 → 다음 실험은 항상 Cold Cache
}

int main() {
    system("mkdir -p ./results");

    WorkloadGenerator gen(NUM_KEYS);

    // ── 실험 1: 분포별 Hit Rate (캐시 32MB 고정) ──────────
    std::vector<std::pair<std::string, std::vector<int>>> workloads = {
        {"Gaussian_s10", gen.gaussian(NUM_REQUESTS, 0.5, 0.10)},
        {"Gaussian_s05", gen.gaussian(NUM_REQUESTS, 0.5, 0.05)},
        {"Zipfian_a10",  gen.zipfian(NUM_REQUESTS,  1.0)},
        {"Zipfian_a05",  gen.zipfian(NUM_REQUESTS,  0.5)},
        {"Hotspot_8020", gen.hotspot(NUM_REQUESTS,  0.20, 0.80)},
        {"Hotspot_9505", gen.hotspot(NUM_REQUESTS,  0.05, 0.95)},
    };

    std::ofstream csv("./results/custom_dist.csv");
    csv << "workload,cache_mb,hit,miss,hit_rate\n";

    std::cout << "\n[실험 1] 분포별 Hit Rate (Cache=32MB)\n";
    std::cout << std::string(55, '=') << "\n";

    for (auto& [name, keys] : workloads) {
        // DB를 새로 열기 → 완전한 Cold Cache 상태 보장
        CacheResult r = measure(32 * 1024 * 1024, keys);

        std::cout << std::left  << std::setw(18) << name
                  << " Hit="   << std::setw(8)  << r.hit
                  << " Miss="  << std::setw(8)  << r.miss
                  << " Rate="  << std::fixed << std::setprecision(2)
                  << r.rate()  << "%\n";

        csv << name << ",32," << r.hit << "," << r.miss << ","
            << r.rate() << "\n";
    }

    // ── 실험 2: 캐시 크기 Sweep (Gaussian σ=10% 고정) ─────
    std::ofstream csv2("./results/custom_cache_sweep.csv");
    csv2 << "workload,cache_mb,hit,miss,hit_rate\n";

    std::cout << "\n[실험 2] 캐시 크기별 Hit Rate (Gaussian σ=10%)\n";
    std::cout << std::string(55, '=') << "\n";

    auto gauss_keys = gen.gaussian(NUM_REQUESTS, 0.5, 0.10);

    for (int mb : {4, 8, 16, 32, 64, 128, 256}) {
        // 캐시 크기마다 DB 새로 열기 → Cold Cache 보장
        CacheResult r = measure((size_t)mb * 1024 * 1024, gauss_keys);

        std::cout << "  Cache " << std::setw(4) << mb
                  << " MB → "  << r.rate() << "%\n";

        csv2 << "Gaussian_s10," << mb << "," << r.hit << ","
             << r.miss << "," << r.rate() << "\n";
    }

    std::cout << "\n✓ results/custom_dist.csv\n";
    std::cout << "✓ results/custom_cache_sweep.csv\n";
    return 0;
}