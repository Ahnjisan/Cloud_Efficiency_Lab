import http from "k6/http";
import { Counter } from "k6/metrics";

const successes = new Counter("successful_requests");
export const options = {
    scenarios: {
        peak: {
            executor: "constant-arrival-rate",
            rate: 25,
            timeUnit: "1s",
            duration: "12s",
            preAllocatedVUs: 3,
            maxVUs: 3,
            gracefulStop: "2s",
        },
    },
    summaryTrendStats: ["p(95)", "p(99)"],
};

export default function () {
    const response = http.get(__ENV.LOCAL_URL + "/work", { timeout: "2s" });
    if (response.status === 200) successes.add(1);
}
