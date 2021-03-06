# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Internal utilities."""

from contextlib import contextmanager
from time import time

import grpc

from opentelemetry.sdk.metrics import Counter, ValueRecorder


class RpcInfo:
    def __init__(
        self,
        full_method=None,
        metadata=None,
        timeout=None,
        request=None,
        response=None,
        error=None,
    ):
        self.full_method = full_method
        self.metadata = metadata
        self.timeout = timeout
        self.request = request
        self.response = response
        self.error = error


class TimedMetricRecorder:
    def __init__(self, meter, span_kind):
        self._meter = meter
        service_name = "grpcio"
        self._span_kind = span_kind
        base_attributes = ["method"]

        if self._meter:
            self._duration = self._meter.create_metric(
                name="{}/{}/duration".format(service_name, span_kind),
                description="Duration of grpc requests to the server",
                unit="ms",
                value_type=float,
                metric_type=ValueRecorder,
                label_keys=base_attributes + ["error", "status_code"],
            )
            self._error_count = self._meter.create_metric(
                name="{}/{}/errors".format(service_name, span_kind),
                description="Number of errors that were returned from the server",
                unit="1",
                value_type=int,
                metric_type=Counter,
                label_keys=base_attributes + ["status_code"],
            )
            self._bytes_in = self._meter.create_metric(
                name="{}/{}/bytes_in".format(service_name, span_kind),
                description="Number of bytes received from the server",
                unit="by",
                value_type=int,
                metric_type=Counter,
                label_keys=base_attributes,
            )
            self._bytes_out = self._meter.create_metric(
                name="{}/{}/bytes_out".format(service_name, span_kind),
                description="Number of bytes sent out through gRPC",
                unit="by",
                value_type=int,
                metric_type=Counter,
                label_keys=base_attributes,
            )

    def record_bytes_in(self, bytes_in, method):
        if self._meter:
            labels = {"method": method}
            self._bytes_in.add(bytes_in, labels)

    def record_bytes_out(self, bytes_out, method):
        if self._meter:
            labels = {"method": method}
            self._bytes_out.add(bytes_out, labels)

    @contextmanager
    def record_latency(self, method):
        start_time = time()
        labels = {"method": method, "status_code": grpc.StatusCode.OK}
        try:
            yield labels
        except grpc.RpcError as exc:
            if self._meter:
                # pylint: disable=no-member
                labels["status_code"] = exc.code()
                self._error_count.add(1, labels)
                labels["error"] = True
            raise
        finally:
            if self._meter:
                if "error" not in labels:
                    labels["error"] = False
                elapsed_time = (time() - start_time) * 1000
                self._duration.record(elapsed_time, labels)
