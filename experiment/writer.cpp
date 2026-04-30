#include <iostream>
#include <string>
#include <cstdio>

#include "rocksdb/db.h"
#include "rocksdb/options.h"
#include "rocksdb/table.h"

using namespace ROCKSDB_NAMESPACE;

const int   NUM_KEYS   = 100000;
const int   VALUE_SIZE = 1024;
const char* DB_PATH    = "/tmp/rocksdb_exp_db";

std::string make_key(int id) {
    char buf[32];
    snprintf(buf, sizeof(buf), "key_%07d", id);
    return buf;
}

int main() {
    std::cout << "[Writer] DB 초기화 중...\n";

    // 기존 DB 삭제
    system(("rm -rf " + std::string(DB_PATH)).c_str());

    // ── Block Cache 없이 쓰기 (쓰기 과정에서 캐시 오염 방지) ──
    BlockBasedTableOptions topt;
    topt.no_block_cache = true;   // ← 캐시 완전 비활성화

    Options opt;
    opt.table_factory.reset(NewBlockBasedTableFactory(topt));
    opt.create_if_missing = true;
    opt.write_buffer_size = 64 * 1024 * 1024;

    std::unique_ptr<DB> db;
    Status s = DB::Open(opt, DB_PATH, &db);
    if (!s.ok()) {
        std::cerr << "DB Open 실패: " << s.ToString() << "\n";
        return 1;
    }

    // ── 데이터 삽입 ──────────────────────────────────────
    WriteOptions wo;
    wo.disableWAL = true;
    std::string val(VALUE_SIZE, 'v');

    std::cout << "[Writer] " << NUM_KEYS << "개 키 삽입 중...\n";
    for (int i = 0; i < NUM_KEYS; i++) {
        db->Put(wo, make_key(i), val);
        if (i % 20000 == 0)
            std::cout << "  " << i << " / " << NUM_KEYS << "\n";
    }

    // ── SST 파일로 강제 Flush ──────────────────────────
    // 이 시점에 MemTable → SST 파일로 이동
    std::cout << "[Writer] Flush 중 (MemTable → SST)...\n";
    db->Flush(FlushOptions());

    // ── Compaction으로 L0 → L1 정리 ───────────────────
    // SST 파일 구조를 깔끔하게 정리
    std::cout << "[Writer] Compaction 중...\n";
    db->CompactRange(CompactRangeOptions(), nullptr, nullptr);

    std::cout << "[Writer] 완료. DB 경로: " << DB_PATH << "\n";
    std::cout << "[Writer] 프로그램 종료 → 메모리 해제\n";

    // unique_ptr 소멸 → DB 완전 닫힘
    return 0;
    // ↑ 여기서 프로세스 종료 → MemTable 포함 모든 메모리 해제
}