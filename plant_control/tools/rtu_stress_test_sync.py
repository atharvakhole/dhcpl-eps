"""
Modbus RTU Sequential Test - Direct Serial Connection
Tests performance without gateway overhead
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict
import statistics

from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException


@dataclass
class ReadResult:
    """Single read operation result"""
    slave_id: int
    iteration: int
    registers: List[int]
    success: bool
    duration_ms: float
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class SlaveMetrics:
    """Metrics for one slave"""
    slave_id: int
    total_reads: int
    successful_reads: int
    failed_reads: int
    success_rate: float
    avg_duration_ms: float
    median_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    total_duration_ms: float


@dataclass
class OverallMetrics:
    """System-wide metrics"""
    total_slaves: int
    total_reads: int
    successful_reads: int
    failed_reads: int
    overall_success_rate: float
    total_duration_seconds: float
    overall_requests_per_second: float
    avg_duration_ms: float
    median_duration_ms: float


class ModbusRTUSequentialTester:
    """Sequential test with direct RTU connection"""
    
    def __init__(
        self,
        port: str,
        baudrate: int,
        slave_ids: List[int],
        registers: List[int],
        iterations_per_slave: int,
        timeout: float = 1.0,
        delay_between_reads: float = 0.0
    ):
        self.port = port
        self.baudrate = baudrate
        self.slave_ids = slave_ids
        self.registers = registers
        self.iterations_per_slave = iterations_per_slave
        self.timeout = timeout
        self.delay_between_reads = delay_between_reads
        
        self.client: Optional[ModbusSerialClient] = None
        self.results: List[ReadResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
    def connect(self) -> bool:
        """Connect to serial port"""
        try:
            self.client = ModbusSerialClient(
                port=self.port,
                baudrate=self.baudrate,
                parity='N',
                stopbits=1,
                bytesize=8,
                timeout=self.timeout
            )
            connected = self.client.connect()
            if connected:
                print(f"✓ Connected to {self.port} at {self.baudrate} baud")
            else:
                print(f"✗ Failed to connect to {self.port}")
            return connected
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from serial port"""
        if self.client:
            self.client.close()
            print("✓ Disconnected")
    
    def read_registers_from_slave(
        self,
        slave_id: int,
        iteration: int
    ) -> ReadResult:
        """Read registers from a specific slave"""
        start = time.time()
        
        try:
            response = self.client.read_holding_registers(
                address=min(self.registers),
                count=max(self.registers) - min(self.registers) + 1,
                slave=slave_id
            )
            
            duration_ms = (time.time() - start) * 1000
            
            if response.isError():
                return ReadResult(
                    slave_id=slave_id,
                    iteration=iteration,
                    registers=[],
                    success=False,
                    duration_ms=duration_ms,
                    error=str(response)
                )
            
            values = []
            for reg in self.registers:
                idx = reg - min(self.registers)
                if idx < len(response.registers):
                    values.append(response.registers[idx])
            
            return ReadResult(
                slave_id=slave_id,
                iteration=iteration,
                registers=values,
                success=True,
                duration_ms=duration_ms
            )
            
        except ModbusException as e:
            duration_ms = (time.time() - start) * 1000
            return ReadResult(
                slave_id=slave_id,
                iteration=iteration,
                registers=[],
                success=False,
                duration_ms=duration_ms,
                error=f"ModbusException: {str(e)}"
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return ReadResult(
                slave_id=slave_id,
                iteration=iteration,
                registers=[],
                success=False,
                duration_ms=duration_ms,
                error=f"Exception: {str(e)}"
            )
    
    def run_sequential_test(self):
        """Run all read operations sequentially"""
        print(f"\n{'='*80}")
        print(f"DIRECT RTU SEQUENTIAL TEST:")
        print(f"  Port: {self.port}")
        print(f"  Baudrate: {self.baudrate}")
        print(f"  Slaves: {len(self.slave_ids)} (IDs: {self.slave_ids})")
        print(f"  Iterations per slave: {self.iterations_per_slave}")
        print(f"  Total operations: {len(self.slave_ids) * self.iterations_per_slave}")
        print(f"  Registers: {self.registers}")
        print(f"  Delay between reads: {self.delay_between_reads}s")
        print(f"{'='*80}\n")
        
        if not self.connect():
            print("Failed to connect. Aborting test.")
            return
        
        self.start_time = time.time()
        
        try:
            for slave_id in self.slave_ids:
                print(f"\nTesting Slave {slave_id}...")
                
                for iteration in range(self.iterations_per_slave):
                    result = self.read_registers_from_slave(slave_id, iteration)
                    self.results.append(result)
                    
                    if iteration % 10 == 0 or iteration == self.iterations_per_slave - 1:
                        success_count = sum(1 for r in self.results if r.success and r.slave_id == slave_id)
                        print(f"  Iteration {iteration + 1}/{self.iterations_per_slave} "
                              f"({success_count} successful, {result.duration_ms:.1f}ms)")
                    
                    if self.delay_between_reads > 0:
                        time.sleep(self.delay_between_reads)
                
                slave_results = [r for r in self.results if r.slave_id == slave_id]
                successful = [r for r in slave_results if r.success]
                print(f"  ✓ Slave {slave_id} complete: {len(successful)}/{len(slave_results)} successful")
        
        finally:
            self.end_time = time.time()
            self.disconnect()
        
        print(f"\n{'='*80}")
        print(f"Test completed in {self.end_time - self.start_time:.2f} seconds")
        print(f"{'='*80}\n")
    
    def calculate_slave_metrics(self) -> Dict[int, SlaveMetrics]:
        """Calculate metrics per slave"""
        slave_results = defaultdict(list)
        
        for result in self.results:
            slave_results[result.slave_id].append(result)
        
        metrics = {}
        for slave_id, results in slave_results.items():
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            durations = [r.duration_ms for r in successful]
            
            if durations:
                total_duration_ms = sum(durations)
                metrics[slave_id] = SlaveMetrics(
                    slave_id=slave_id,
                    total_reads=len(results),
                    successful_reads=len(successful),
                    failed_reads=len(failed),
                    success_rate=len(successful) / len(results) * 100,
                    avg_duration_ms=statistics.mean(durations),
                    median_duration_ms=statistics.median(durations),
                    min_duration_ms=min(durations),
                    max_duration_ms=max(durations),
                    total_duration_ms=total_duration_ms
                )
        
        return metrics
    
    def calculate_overall_metrics(self, slave_metrics: Dict[int, SlaveMetrics]) -> OverallMetrics:
        """Calculate overall system metrics"""
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        durations = [r.duration_ms for r in successful]
        
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        return OverallMetrics(
            total_slaves=len(self.slave_ids),
            total_reads=len(self.results),
            successful_reads=len(successful),
            failed_reads=len(failed),
            overall_success_rate=len(successful) / len(self.results) * 100 if self.results else 0,
            total_duration_seconds=total_duration,
            overall_requests_per_second=len(successful) / total_duration if total_duration > 0 else 0,
            avg_duration_ms=statistics.mean(durations) if durations else 0,
            median_duration_ms=statistics.median(durations) if durations else 0
        )
    
    def print_results(self):
        """Print comprehensive test results"""
        slave_metrics = self.calculate_slave_metrics()
        overall_metrics = self.calculate_overall_metrics(slave_metrics)
        
        print("\n" + "="*80)
        print("OVERALL METRICS - DIRECT RTU SEQUENTIAL TEST")
        print("="*80)
        print(f"Connection: {self.port} @ {self.baudrate} baud")
        print(f"Total Test Duration:        {overall_metrics.total_duration_seconds:.2f} seconds")
        print(f"Total Slaves:               {overall_metrics.total_slaves}")
        print(f"Total Read Operations:      {overall_metrics.total_reads}")
        print(f"Successful Reads:           {overall_metrics.successful_reads}")
        print(f"Failed Reads:               {overall_metrics.failed_reads}")
        print(f"Overall Success Rate:       {overall_metrics.overall_success_rate:.2f}%")
        print(f"Overall Throughput:         {overall_metrics.overall_requests_per_second:.2f} req/s")
        print(f"Average Response Time:      {overall_metrics.avg_duration_ms:.2f} ms")
        print(f"Median Response Time:       {overall_metrics.median_duration_ms:.2f} ms")
        
        print("\n" + "="*80)
        print("PER-SLAVE METRICS")
        print("="*80)
        for slave_id in sorted(slave_metrics.keys()):
            metrics = slave_metrics[slave_id]
            print(f"\nSlave {slave_id}:")
            print(f"  Total Reads:              {metrics.total_reads}")
            print(f"  Successful:               {metrics.successful_reads}")
            print(f"  Failed:                   {metrics.failed_reads}")
            print(f"  Success Rate:             {metrics.success_rate:.2f}%")
            print(f"  Avg Response Time:        {metrics.avg_duration_ms:.2f} ms")
            print(f"  Median Response Time:     {metrics.median_duration_ms:.2f} ms")
            print(f"  Min Response Time:        {metrics.min_duration_ms:.2f} ms")
            print(f"  Max Response Time:        {metrics.max_duration_ms:.2f} ms")
        
        failed_results = [r for r in self.results if not r.success]
        if failed_results:
            print("\n" + "="*80)
            print("ERROR SUMMARY")
            print("="*80)
            error_counts = defaultdict(int)
            for result in failed_results:
                error_counts[result.error] += 1
            
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {count}x: {error}")
        
        print("\n" + "="*80)


def main():
    """Run the direct RTU sequential test"""
    
    # CONFIGURATION
    PORT = '/dev/ttyACM0'  # Change for your system
    BAUDRATE = 19200
    SLAVE_IDS = [1, 4, 3]
    REGISTERS = [100]
    ITERATIONS_PER_SLAVE = 100
    TIMEOUT = 1.0
    DELAY_BETWEEN_READS = 0.0
    
    tester = ModbusRTUSequentialTester(
        port=PORT,
        baudrate=BAUDRATE,
        slave_ids=SLAVE_IDS,
        registers=REGISTERS,
        iterations_per_slave=ITERATIONS_PER_SLAVE,
        timeout=TIMEOUT,
        delay_between_reads=DELAY_BETWEEN_READS
    )
    
    tester.run_sequential_test()
    tester.print_results()


if __name__ == "__main__":
    main()
