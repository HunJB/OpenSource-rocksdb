#pragma once
#include <random>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <ctime> 

class WorkloadGenerator {
    int num_keys_;
    std::mt19937 rng_;

public:
    //seed 값 랜덤 필요 / 고정 시드 -> sedd = 42등 상수로 변경
    WorkloadGenerator(int num_keys, unsigned seed = (unsigned)std::time(nullptr))
        : num_keys_(num_keys), rng_(seed) {}


    // ── 분포 함수들 ───────────────────────────────────────

    /*
    workload 추가시...
    **workload_gen.h 에 함수 추가**
    std::vector<int> 새분포이름(int n, 파라미터) {
    // 분포 구현
        std::vector<int> keys(n);
    // ...
    return keys;
        }
    
    */

    // 1. 랜덤
    std::vector<int> uniform(int n) {
        std::uniform_int_distribution<int> d(0, num_keys_ - 1);
        std::vector<int> keys(n);
        for (auto& k : keys) k = d(rng_);
        return keys;
    }

    // 2. 순차
    std::vector<int> sequential(int n) {
        std::vector<int> keys(n);
        for (int i = 0; i < n; i++) keys[i] = i % num_keys_;
        return keys;
    }

    // 3. 가우시안
    std::vector<int> gaussian(int n, double mean_r=0.5, double std_r=0.1) {
        std::normal_distribution<double> d(num_keys_*mean_r, num_keys_*std_r);
        std::vector<int> keys;
        keys.reserve(n);
        while ((int)keys.size() < n) {
            int k = (int)d(rng_);
            if (k >= 0 && k < num_keys_) keys.push_back(k);
        }
        return keys;
    }

    // 4. zipfian
    std::vector<int> zipfian(int n, double alpha=1.0) {
        std::vector<double> cdf(num_keys_);
        double sum = 0.0;
        for (int i = 0; i < num_keys_; i++) sum += 1.0/std::pow(i+1, alpha);
        double acc = 0.0;
        for (int i = 0; i < num_keys_; i++) {
            acc += 1.0/std::pow(i+1, alpha);
            cdf[i] = acc/sum;
        }
        std::uniform_real_distribution<double> u(0.0, 1.0);
        std::vector<int> keys(n);
        for (auto& k : keys) {
            double r = u(rng_);
            k = (int)(std::lower_bound(cdf.begin(), cdf.end(), r) - cdf.begin());
            if (k >= num_keys_) k = num_keys_-1;
        }
        return keys;
    }

    // 5. hotspot (특정 지역 쏠려있는 분포)
    std::vector<int> hotspot(int n, double hot_key_r=0.2, double hot_req_r=0.8) {
        int hot_max = (int)(num_keys_*hot_key_r);
        std::uniform_int_distribution<int> hot(0, hot_max-1);
        std::uniform_int_distribution<int> cold(hot_max, num_keys_-1);
        std::uniform_real_distribution<double> coin(0.0, 1.0);
        std::vector<int> keys(n);
        for (auto& k : keys) k = (coin(rng_) < hot_req_r) ? hot(rng_) : cold(rng_);
        return keys;
    }

    // 6. bimodal(이중 피크)
    std::vector<int> bimodal(int n, double mean1_r=0.25, double mean2_r=0.75,
                              double std_r=0.05) {
        std::normal_distribution<double> d1(num_keys_*mean1_r, num_keys_*std_r);
        std::normal_distribution<double> d2(num_keys_*mean2_r, num_keys_*std_r);
        std::uniform_real_distribution<double> coin(0.0, 1.0);
        std::vector<int> keys;
        keys.reserve(n);
        while ((int)keys.size() < n) {
            int k = (int)((coin(rng_) < 0.5) ? d1(rng_) : d2(rng_));
            if (k >= 0 && k < num_keys_) keys.push_back(k);
        }
        return keys;
    }

    // 7. latest(시간 지역성)
    std::vector<int> latest(int n, double skewness=0.8) {
        std::uniform_real_distribution<double> u(0.0, 1.0);
        std::vector<int> keys(n);
        for (auto& k : keys) {
            double r = 1.0 - std::pow(u(rng_), 1.0/skewness);
            k = std::clamp((int)(r * num_keys_), 0, num_keys_-1);
        }
        return keys;
    }

    // 모든 workload를 자동으로 반환 ────────────
    // workload_gen.h에 분포를 추가하면 여기에만 추가하면 됨
    // reader.cpp는 수정 불필요
    std::vector<std::pair<std::string, std::vector<int>>>
    get_all_workloads(int n) {
        return {
            {"Uniform",      uniform(n)},
            {"Sequential",   sequential(n)},
            {"Gaussian_s10", gaussian(n, 0.5, 0.10)},
            {"Gaussian_s05", gaussian(n, 0.5, 0.05)},
            {"Zipfian_a10",  zipfian(n,  1.0)},
            {"Zipfian_a05",  zipfian(n,  0.5)},
            {"Hotspot_8020", hotspot(n,  0.20, 0.80)},
            {"Hotspot_9505", hotspot(n,  0.05, 0.95)},
            {"Bimodal",      bimodal(n)},
            {"Latest",       latest(n)},
            //{"새분포이름",    새분포이름(n)}, ← 이 한 줄만 추가
        };
    }
};