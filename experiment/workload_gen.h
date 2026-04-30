#pragma once
#include <random>
#include <vector>
#include <cmath>
#include <algorithm>

class WorkloadGenerator {
    int num_keys_;
    std::mt19937 rng_;

public:
    WorkloadGenerator(int num_keys, unsigned seed = 42)
        : num_keys_(num_keys), rng_(seed) {}

    // 1. Uniform: 모든 키 동일 확률
    std::vector<int> uniform(int n) {
        std::uniform_int_distribution<int> d(0, num_keys_ - 1);
        std::vector<int> keys(n);
        for (auto& k : keys) k = d(rng_);
        return keys;
    }

    // 2. Gaussian: 중앙 키에 집중
    std::vector<int> gaussian(int n, double mean_r = 0.5, double std_r = 0.1) {
        std::normal_distribution<double> d(num_keys_ * mean_r,
                                           num_keys_ * std_r);
        std::vector<int> keys;
        keys.reserve(n);
        while ((int)keys.size() < n) {
            int k = (int)d(rng_);
            if (k >= 0 && k < num_keys_)
                keys.push_back(k);
        }
        return keys;
    }

    // 3. Zipfian: 소수 인기 키에 극집중 (실제 DB 워크로드와 유사)
    std::vector<int> zipfian(int n, double alpha = 1.0) {
        // CDF 테이블 미리 계산 (성능 최적화)
        std::vector<double> cdf(num_keys_);
        double sum = 0.0;
        for (int i = 0; i < num_keys_; i++)
            sum += 1.0 / std::pow(i + 1, alpha);
        double acc = 0.0;
        for (int i = 0; i < num_keys_; i++) {
            acc += 1.0 / std::pow(i + 1, alpha);
            cdf[i] = acc / sum;
        }

        std::uniform_real_distribution<double> u(0.0, 1.0);
        std::vector<int> keys(n);
        for (auto& k : keys) {
            double r = u(rng_);
            // 이진 탐색으로 키 결정
            k = (int)(std::lower_bound(cdf.begin(), cdf.end(), r) - cdf.begin());
            if (k >= num_keys_) k = num_keys_ - 1;
        }
        return keys;
    }

    // 4. Hotspot: hot zone에 요청 집중 (80/20 법칙)
    std::vector<int> hotspot(int n, double hot_key_r = 0.2,
                             double hot_req_r = 0.8) {
        int hot_max = (int)(num_keys_ * hot_key_r);
        std::uniform_int_distribution<int> hot(0, hot_max - 1);
        std::uniform_int_distribution<int> cold(hot_max, num_keys_ - 1);
        std::uniform_real_distribution<double> coin(0.0, 1.0);

        std::vector<int> keys(n);
        for (auto& k : keys)
            k = (coin(rng_) < hot_req_r) ? hot(rng_) : cold(rng_);
        return keys;
    }

    // 5. Sequential: 순차 접근 (캐시 비효율의 기준점)
    std::vector<int> sequential(int n) {
        std::vector<int> keys(n);
        for (int i = 0; i < n; i++) keys[i] = i % num_keys_;
        return keys;
    }

 
    //6.
};