ROCKSDB_DIR = $(HOME)/rocksdb

CXX      = g++
CXXFLAGS = -std=c++20 -O2 -I$(ROCKSDB_DIR)/include
LDFLAGS  = $(ROCKSDB_DIR)/librocksdb.a \
           -lpthread -ldl -lz -lbz2 -lsnappy -llz4 -lzstd -lgflags

all: writer reader

writer: writer.cpp
	$(CXX) $(CXXFLAGS) writer.cpp -o writer $(LDFLAGS)

reader: reader.cpp workload_gen.h
	$(CXX) $(CXXFLAGS) reader.cpp -o reader $(LDFLAGS)

clean:
	rm -f writer reader
	rm -rf results/*.csv results/*.png