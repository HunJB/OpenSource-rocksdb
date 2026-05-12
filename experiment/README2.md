# RocksDB 캐시 히트율 실험 가이드

## 디렉토리 구조

```
experiment/
├── writer.cpp            # DB 초기화 (키 100,000개 삽입)
├── reader.cpp            # 실험 실행 (정적·동적 분포, 캐시 스윕)
├── reader_adv.cpp        # 추가 실험 (BLOCK_CACHE_DATA_HIT 기반 측정)
├── workload_gen.h        # 워크로드 분포 정의
├── Makefile              # 빌드
│
├── run_experiments.sh    # 병렬 실험 실행 (메인 실행 스크립트)
├── run_bench.sh          # db_bench 기반 추가 실험
├── step_experiments.sh   # 단계적 실험 (n회씩 늘려가며 자동 실행)
│
├── plot.py               # 정적 분포 그래프 생성
├── plot2.py              # 동적 분포 배치별 시계열 그래프 생성
├── plot_adv.py           # reader_adv 결과 그래프 생성
├── aggregate.py          # 전체 실험 결과 통합 그래프 생성
│
└── results/
    ├── exp_data/
    │   ├── latest_run.txt          # 최근 실험 ID
    │   ├── latest_adv_run.txt      # 최근 reader_adv 실험 ID
    │   └── run_<ID>/               # 실험별 결과 폴더
    │       ├── meta.txt
    │       ├── custom_dist.csv         # 실험1: 분포별 hit rate (32MB)
    │       ├── custom_cache_sweep.csv  # 실험2: 캐시 크기별 스윕
    │       ├── showdist.csv            # 실험0: 키 접근 빈도 분포
    │       ├── custom_movedist.csv     # 실험2-1: 동적 분포 hit rate
    │       ├── custom_movedist_batch.csv # 실험2-2: 배치별 시계열
    │       └── dbbench_results.csv     # (선택) db_bench 결과
    └── graph/
        └── run_<ID>/               # 실험별 그래프 폴더
    └── aggregated/                 # aggregate.py 통합 그래프
```

---

## 빌드

```bash
make clean && make
```

생성 바이너리: `writer`, `reader`, `reader_adv`

---

## 실험 파라미터

| 상수 | 값 | 설명 |
|---|---|---|
| `NUM_KEYS` | 100,000 | DB에 삽입되는 키 총 수 |
| `NUM_REQUESTS` | 50,000 | 실험당 읽기 요청 수 |
| `BATCH` | 5,000 | 배치 1개당 요청 수 |
| `BATCH_NUM` | 10 | 배치 수 (BATCH × BATCH_NUM = NUM_REQUESTS) |
| 캐시 스윕 | 4, 8, 16, 32, 64, 128, 256 MB | 실험2 캐시 크기 목록 |

---

## 워크로드 분포 (`workload_gen.h`)

### 정적 분포 (접근 패턴이 실험 내내 동일)

| 이름 | 설명 |
|---|---|
| `Uniform` | 전체 키 공간 균등 랜덤 |
| `Sequential` | 순차 접근 (0, 1, 2, ...) |
| `Gaussian_s10` | 가우시안, 표준편차 10% |
| `Gaussian_s05` | 가우시안, 표준편차 5% |
| `Zipfian_a10` | 지프 분포, α=1.0 (강한 쏠림) |
| `Zipfian_a05` | 지프 분포, α=0.5 (약한 쏠림) |
| `Hotspot_8020` | 상위 20% 키에 요청 80% 집중 |
| `Hotspot_9505` | 상위 5% 키에 요청 95% 집중 |
| `Bimodal` | 이중 피크 (25%, 75% 구간) |
| `Latest` | 최근 키 우선 (시간 지역성) |

### 동적 분포 (배치 진행에 따라 접근 패턴이 이동)

| 이름 | 전반부 중심 | 후반부 중심 | 표준편차 |
|---|---|---|---|
| `moving_gaussian030710` | 30% | 70% | 10% |
| `moving_gaussian020810` | 20% | 80% | 10% |
| `moving_gaussian030705` | 30% | 70% | 5% |
| `moving_gaussian020805` | 20% | 80% | 5% |

> 전반부 25,000건은 첫 번째 피크, 후반부 25,000건은 두 번째 피크 분포를 따름

---

## 실험 흐름

### 1단계: DB 초기화 (최초 1회)

```bash
./writer
```

- `/tmp/rocksdb_exp_db`에 키 100,000개 (값 1KB) 삽입
- Flush + CompactRange로 MemTable을 SST로 완전 내림
- 이후 reader 측정 시 MemTable 영향 없음 (MEMTABLE_HIT = 0 검증 완료)

---

### 2단계: 실험 실행

#### 방법 A — 단일 실행

```bash
./reader
```

- 실험 결과를 `results/exp_data/run_<타임스탬프_PID>/`에 저장
- `latest_run.txt` 갱신

#### 방법 B — 병렬 실행 (권장)

```bash
./run_experiments.sh [실험수] [병렬슬롯수] [--bench]
```

| 인자 | 기본값 | 설명 |
|---|---|---|
| 실험수 | 10 | 총 reader 실행 횟수 |
| 병렬슬롯수 | CPU 코어 수 | 동시 실행 수 (DB 하드링크 복사) |
| `--bench` | 없음 | 완료 후 db_bench 1회 실행 |

예시:
```bash
./run_experiments.sh 20 4          # 20회 실험, 4슬롯 병렬
./run_experiments.sh 100 8 --bench # 100회 실험, 8슬롯, db_bench 포함
```

#### 방법 C — 단계적 자동 실험

```bash
./step_experiments.sh [시작] [끝] [단계] [병렬수]
```

| 인자 | 기본값 | 설명 |
|---|---|---|
| 시작 | 10 | 첫 번째 마일스톤 실험 횟수 |
| 끝 | 50 | 마지막 마일스톤 실험 횟수 |
| 단계 | 5 | 각 마일스톤 간격 |
| 병렬수 | CPU 코어 수 | 동시 실행 수 |

예시:
```bash
./step_experiments.sh              # 10→50, 5단위 (기본값)
./step_experiments.sh 10 30 10 4   # 10→30, 10단위, 4슬롯
```

> 각 마일스톤 완료 시 `aggregate.py` 자동 실행하여 중간 집계 그래프 저장

---

### 3단계: 그래프 생성

#### 정적 분포 실험 결과

```bash
python3 plot.py [run_id]
```

- 인자 생략 시 `latest_run.txt` 참조
- 출력: `results/graph/run_<ID>/` 하위 PNG 파일들

#### 동적 분포 배치별 시계열

```bash
python3 plot2.py [run_id]
```

- 인자 생략 시 `latest_run.txt` 참조
- 출력: `results/graph/run_<ID>/hit_rate_by_batch.png`
- `custom_movedist_batch.csv` 기반 (배치 번호별 hit rate 꺾은선 그래프)

#### reader_adv 결과

```bash
python3 plot_adv.py [run_id]
```

- 인자 생략 시 `latest_adv_run.txt` 참조

#### 전체 실험 통합 집계

```bash
python3 aggregate.py
```

- 모든 `run_*` 폴더의 CSV를 통합하여 평균·표준편차 계산
- 출력: `results/aggregated/` 하위 PNG 파일들

---

## 실험별 출력 CSV 형식

### `custom_dist.csv` — 정적 분포별 hit rate (32MB 고정)

```
workload,cache_mb,hit,miss,hit_rate
Uniform,32,12345,37655,24.69
...
```

### `custom_cache_sweep.csv` — 캐시 크기 스윕

```
workload,cache_mb,hit,miss,hit_rate
Uniform,4,3210,46790,6.42
Uniform,8,5430,44570,10.86
...
```

### `showdist.csv` — 키 접근 빈도 분포 (50구간 히스토그램)

```
workload,area0,area1,...,area49
Uniform,1047,1070,...
Sequential,2000,2000,...
```

### `custom_movedist.csv` — 동적 분포 hit rate (32MB)

```
workload,cache_mb,hit,miss,hit_rate
moving_gaussian030710,32,28400,21600,56.8
...
```

### `custom_movedist_batch.csv` — 배치별 시계열

```
workload,cache_mb,batch,hit,miss,hit_rate
moving_gaussian030710,32,0,1174,3826,23.48
moving_gaussian030710,32,1,2708,2292,54.16
...
```

> `batch` 0~9: 배치가 진행될수록 캐시가 워밍업되며 hit rate가 변화하는 양상 관찰 가능

---

## 워크로드 추가 방법

### 정적 분포 추가

1. `workload_gen.h`에 분포 함수 추가
2. `get_static_workloads()`에 한 줄 추가

```cpp
// workload_gen.h
std::vector<int> my_dist(int n) { ... }

// get_static_workloads() 내부
{"MyDist", my_dist(n)},
```

### 동적 분포 추가

1. `workload_gen.h`에 분포 함수 추가
2. `get_dynamic_workloads()`에 한 줄 추가

```cpp
{"my_dynamic", my_dynamic(n, param1, param2)},
```

> `reader.cpp`는 수정 불필요. `workload_gen.h`만 변경하면 모든 실험에 자동 반영됨.

---

## 환경변수 (병렬 실행 시 내부 사용)

| 변수 | 설명 |
|---|---|
| `READER_DB_PATH` | reader가 열 DB 경로 (슬롯별 하드링크 DB) |
| `READER_RUN_ID` | 실험 ID (reader와 reader_adv가 같은 폴더 공유) |

`run_experiments.sh`가 자동으로 설정하므로 직접 지정 불필요.

---

## 전체 실행 예시 (처음부터)

```bash
# 1. 빌드
make clean && make

# 2. DB 초기화
./writer

# 3. 실험 실행 (20회, 4슬롯 병렬)
./run_experiments.sh 20 4

# 4. 그래프 생성
python3 plot.py
python3 plot2.py
python3 aggregate.py
```
