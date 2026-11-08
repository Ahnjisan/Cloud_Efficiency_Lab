"""Shared safeguards for the Windows live experiment runners."""
import math
import time


def pin_local_docker(command, env):
    if env.get("DOCKER_HOST"):
        raise RuntimeError("unset DOCKER_HOST before running the local experiment")
    context = command(["docker", "context", "show"]).strip()
    endpoint = command(["docker", "context", "inspect", "--format",
                        "{{.Endpoints.docker.Host}}", "--", context]).strip()
    if endpoint not in ("npipe:////./pipe/dockerDesktopLinuxEngine", "npipe:////./pipe/docker_engine"):
        raise RuntimeError("Docker context must resolve to a supported local Windows named pipe")
    pinned = env.copy()
    for key in ("DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"):
        pinned.pop(key, None)
    pinned["DOCKER_HOST"] = endpoint
    return pinned


def cleanup_owned(command, scope, minikube=False):
    label = "infrafit.run=" + scope
    profile_label = "name.minikube.sigs.k8s.io=" + scope

    def find(kind, selector):
        listing = ["ps", "-aq"] if kind == "container" else [kind, "ls", "-q"]
        return set(command(["docker", *listing, "--filter", selector], monitor=False).split())

    clear = False
    for _ in range(4):
        try:
            containers = find("container", "label=" + label)
            networks = find("network", "label=" + label)
            volumes = set()
            if minikube:
                containers |= find("container", "label=" + profile_label)
                networks |= find("network", "label=" + profile_label)
                volumes = find("volume", "label=" + profile_label)
                # The preload extractor can be unnamed and identified only by its dedicated volume.
                for volume in volumes:
                    containers |= find("container", "volume=" + volume)
            residual = (containers or networks or volumes
                        or find("container", "name=^/?" + scope + "($|-)")
                        or find("network", "name=^" + scope + "$")
                        or (minikube and find("volume", "name=^" + scope + "$")))
            if not residual and clear:
                return True
            clear = not residual
            for kind, ids in (("container", containers), ("volume", volumes), ("network", networks)):
                if ids:
                    force = ["-f"] if kind == "container" else []
                    command(["docker", kind, "rm", *force, *sorted(ids)], checked=False, monitor=False)
        except (OSError, RuntimeError):
            clear = False
        time.sleep(1)
    return False


def validate_measurement(run, expected_mcpu, target_requests=750):
    def number(value):
        return type(value) in (int, float) and math.isfinite(value)

    try:
        metrics = run["k6"]["metrics"]
        successes = metrics["successful_requests"]["count"]
        rate = metrics["successful_requests"]["rate"]
        requests = metrics["http_reqs"]["count"]
        errors = metrics["http_req_failed"]
        error_rate = errors.get("rate", errors.get("value"))
        latency = metrics["http_req_duration"]
        p95, p99 = latency["p(95)"], latency["p(99)"]
        dropped = metrics.get("dropped_iterations", {}).get("count", 0)
        interval = run["sample_interval_s"]
        if not (
            all(number(value) for value in (successes, requests, rate, error_rate, p95, p99, dropped, interval))
            and int(successes) == successes and int(requests) == requests and 0 < successes <= requests
            and rate > 0 and 0 <= error_rate < 1 and 0 <= p95 <= p99
            and int(dropped) == dropped and dropped >= 0 and interval > 0
        ):
            raise ValueError("invalid k6 measurements")
        max_error_rate = (requests - successes) / requests
        if error_rate > max_error_rate and not math.isclose(error_rate, max_error_rate, abs_tol=1e-12):
            raise ValueError("HTTP failure rate contradicts the successful request count")
        counters = []
        for sample in (run["before"], run["after"]):
            quota, period = map(int, sample["cpu.max"].split())
            if quota <= 0 or period <= 0 or quota * 1000 != period * expected_mcpu:
                raise ValueError("cgroup CPU quota does not match the configured limit")
            cpu = dict(line.split() for line in sample["cpu.stat"].splitlines())
            events = dict(line.split() for line in sample["memory.events"].splitlines())
            values = [int(cpu[key]) for key in ("usage_usec", "nr_throttled", "throttled_usec")]
            values.append(int(events["oom_kill"]))
            current, peak = int(sample["memory.current"]), int(sample["memory.peak"])
            if min(values) < 0 or not 0 <= current <= peak:
                raise ValueError("invalid cgroup measurements")
            counters.append(values)
        if any(after < before for before, after in zip(*counters)):
            raise ValueError("cgroup counters regressed during measurement")
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError("missing or malformed k6/cgroup measurement") from error
    run["measurement_valid"] = True
    run["target_load_met"] = successes >= target_requests and dropped == 0 and error_rate == 0
