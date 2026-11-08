import http from "k6/http";
import { Counter } from "k6/metrics";

const successes = new Counter("successful_requests");
export const options = {
    scenarios: {
        fixed: {
            executor: "constant-arrival-rate",
            rate: 25,
            timeUnit: "1s",
            duration: "30s",
            preAllocatedVUs: 3,
            maxVUs: 3,
            gracefulStop: "2s",
        },
    },
    summaryTrendStats: ["avg", "p(95)", "p(99)", "max"],
};

export default function () {
    const response = http.get(__ENV.LOCAL_URL + "/work", { timeout: "2s" });
    if (response.status === 200) successes.add(1);
}
