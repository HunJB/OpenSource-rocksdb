ROCKSDB_DIR = $(HOME)/rocksdb

CXX      = g++
CXXFLAGS = -std=c++20 -O2 -I$(ROCKSDB_DIR)/include
LDFLAGS  = $(ROCKSDB_DIR)/librocksdb.a \
           -lpthread -ldl -lz -lbz2 -lsnappy -llz4 -lzstd -lgflags

all: experiment

experiment: main.cpp workload_gen.h
	$(CXX) $(CXXFLAGS) main.cpp -o experiment $(LDFLAGS)

run: experiment
	./experiment

clean:
	rm -f experiment
	rm -rf results/*.csv results/*.png