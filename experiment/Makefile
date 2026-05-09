# 수정 : reader_adv 추가

ROCKSDB_DIR = $(HOME)/rocksdb

CXX      = g++
CXXFLAGS = -std=c++20 -O2 -I$(ROCKSDB_DIR)/include
LDFLAGS  = $(ROCKSDB_DIR)/librocksdb.a \
           -lpthread -ldl -lz -lbz2 -lsnappy -llz4 -lzstd -lgflags

# reader_adv를 타겟에 추가
all: writer reader reader_adv

writer: writer.cpp
	$(CXX) $(CXXFLAGS) writer.cpp -o writer $(LDFLAGS)

reader: reader.cpp workload_gen.h
	$(CXX) $(CXXFLAGS) reader.cpp -o reader $(LDFLAGS)

# reader_adv 빌드 규칙 추가
reader_adv: reader_adv.cpp workload_gen.h
	$(CXX) $(CXXFLAGS) reader_adv.cpp -o reader_adv $(LDFLAGS)

# 빌드 결과물만 삭제 (실험 결과 보존)
clean:
	rm -f writer reader reader_adv

# 실험 결과까지 삭제할 때만 사용

cleanall:
	rm -f writer reader reader_adv
	rm -rf results/graph/run_*/
	rm -rf results/exp_data/run_*/
	rm -f  results/exp_data/latest_run.txt
	rm -f  results/exp_data/*_meta.txt
