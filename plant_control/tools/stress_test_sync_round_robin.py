"""
Modbus RS485 Interleaved Sequential Test
Tests sequential reads with frequent slave switching
Single client, but alternates between slaves each iteration
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict
import statistics

from pymodbus.client import ModbusTcpClient
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
    operation_number: int = 0  # Track global operation order


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
    requests_per_second: float


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
    slowest_slave: int
    fastest_slave: int


class ModbusInterleavedTester:
    """Interleaved sequential test - switches slaves every read"""
    
    def __init__(
        self,
        host: str,
        port: int,
        slave_ids: List[int],
        registers: List[int],
        iterations: int,
        timeout: float = 5.0,
        delay_between_reads: float = 0.0
    ):
        self.host = host
        self.port = port
        self.slave_ids = slave_ids
        self.registers = registers
        self.iterations = iterations  # Number of complete cycles through all slaves
        self.timeout = timeout
        self.delay_between_reads = delay_between_reads
        
        self.client: Optional[ModbusTcpClient] = None
        self.results: List[ReadResult] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
    def connect(self) -> bool:
        """Connect to Modbus TCP gateway"""
        try:
            self.client = ModbusTcpClient(
                host=self.host,
                port=self.port,
                timeout=self.timeout
            )
            connected = self.client.connect()
            if connected:
                print(f"✓ Connected to {self.host}:{self.port}")
            else:
                print(f"✗ Failed to connect to {self.host}:{self.port}")
            return connected
        except Exception as e:
            print(f"✗ Connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from gateway"""
        if self.client:
            self.client.close()
            print("✓ Disconnected")
    
    def read_registers_from_slave(
        self,
        slave_id: int,
        iteration: int,
        operation_number: int
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
                    error=str(response),
                    operation_number=operation_number
                )
            
            # Extract registers
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
                duration_ms=duration_ms,
                operation_number=operation_number
            )
            
        except ModbusException as e:
            duration_ms = (time.time() - start) * 1000
            return ReadResult(
                slave_id=slave_id,
                iteration=iteration,
                registers=[],
                success=False,
                duration_ms=duration_ms,
                error=f"ModbusException: {str(e)}",
                operation_number=operation_number
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return ReadResult(
                slave_id=slave_id,
                iteration=iteration,
                registers=[],
                success=False,
                duration_ms=duration_ms,
                error=f"Exception: {str(e)}",
                operation_number=operation_number
            )
    
    def run_interleaved_test(self):
        """Run interleaved sequential test - alternates slaves each read"""
        print(f"\n{'='*80}")
        print(f"Starting INTERLEAVED SEQUENTIAL stress test:")
        print(f"  Slaves: {len(self.slave_ids)} (IDs: {self.slave_ids})")
        print(f"  Iterations (full cycles): {self.iterations}")
        print(f"  Total operations: {len(self.slave_ids) * self.iterations}")
        print(f"  Registers to read: {self.registers}")
        print(f"  Target: {self.host}:{self.port}")
        print(f"  Delay between reads: {self.delay_between_reads}s")
        print(f"  Pattern: Slave1→Slave2→...→SlaveN, repeat {self.iterations} times")
        print(f"  Using: SINGLE shared client")
        print(f"{'='*80}\n")
        
        if not self.connect():
            print("Failed to connect. Aborting test.")
            return
        
        self.start_time = time.time()
        total_operations = len(self.slave_ids) * self.iterations
        operation_count = 0
        
        try:
            # INTERLEAVED LOOP: For each iteration, read from all slaves
            for iteration in range(self.iterations):
                print(f"\nIteration {iteration + 1}/{self.iterations}:")
                
                # Read from each slave in sequence
                for slave_id in self.slave_ids:
                    operation_count += 1
                    
                    # Perform read
                    result = self.read_registers_from_slave(
                        slave_id, 
                        iteration,
                        operation_count
                    )
                    self.results.append(result)
                    
                    # Status indicator
                    status = "✓" if result.success else "✗"
                    print(f"  {status} Slave {slave_id}: {result.duration_ms:.1f}ms "
                          f"(op {operation_count}/{total_operations})")
                    
                    # Optional delay between reads
                    if self.delay_between_reads > 0:
                        time.sleep(self.delay_between_reads)
                
                # Summary after each complete cycle
                cycle_results = [r for r in self.results if r.iteration == iteration]
                successful = [r for r in cycle_results if r.success]
                cycle_time = sum(r.duration_ms for r in cycle_results)
                print(f"  Cycle complete: {len(successful)}/{len(cycle_results)} successful, "
                      f"total time: {cycle_time:.1f}ms")
        
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
                    total_duration_ms=total_duration_ms,
                    requests_per_second=len(successful) / (total_duration_ms / 1000)
                )
            else:
                metrics[slave_id] = SlaveMetrics(
                    slave_id=slave_id,
                    total_reads=len(results),
                    successful_reads=0,
                    failed_reads=len(failed),
                    success_rate=0,
                    avg_duration_ms=0,
                    median_duration_ms=0,
                    min_duration_ms=0,
                    max_duration_ms=0,
                    total_duration_ms=0,
                    requests_per_second=0
                )
        
        return metrics
    
    def calculate_overall_metrics(self, slave_metrics: Dict[int, SlaveMetrics]) -> OverallMetrics:
        """Calculate overall system metrics"""
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        durations = [r.duration_ms for r in successful]
        
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        slowest_slave = max(slave_metrics.items(), key=lambda x: x[1].avg_duration_ms)[0] if slave_metrics else 0
        fastest_slave = min(slave_metrics.items(), key=lambda x: x[1].avg_duration_ms)[0] if slave_metrics else 0
        
        return OverallMetrics(
            total_slaves=len(self.slave_ids),
            total_reads=len(self.results),
            successful_reads=len(successful),
            failed_reads=len(failed),
            overall_success_rate=len(successful) / len(self.results) * 100 if self.results else 0,
            total_duration_seconds=total_duration,
            overall_requests_per_second=len(successful) / total_duration if total_duration > 0 else 0,
            avg_duration_ms=statistics.mean(durations) if durations else 0,
            median_duration_ms=statistics.median(durations) if durations else 0,
            slowest_slave=slowest_slave,
            fastest_slave=fastest_slave
        )
    
    def analyze_switching_overhead(self):
        """Analyze if there's overhead when switching between slaves"""
        print("\n" + "="*80)
        print("SLAVE SWITCHING ANALYSIS")
        print("="*80)
        
        # Calculate time when switching vs not switching
        same_slave_times = []
        different_slave_times = []
        
        for i in range(1, len(self.results)):
            current = self.results[i]
            previous = self.results[i - 1]
            
            if not current.success or not previous.success:
                continue
            
            if current.slave_id == previous.slave_id:
                same_slave_times.append(current.duration_ms)
            else:
                different_slave_times.append(current.duration_ms)
        
        if same_slave_times and different_slave_times:
            avg_same = statistics.mean(same_slave_times)
            avg_different = statistics.mean(different_slave_times)
            overhead = avg_different - avg_same
            overhead_pct = (overhead / avg_same) * 100
            
            print(f"\nReads to SAME slave as previous:")
            print(f"  Count:                      {len(same_slave_times)}")
            print(f"  Average time:               {avg_same:.2f} ms")
            print(f"  Median time:                {statistics.median(same_slave_times):.2f} ms")
            
            print(f"\nReads to DIFFERENT slave than previous:")
            print(f"  Count:                      {len(different_slave_times)}")
            print(f"  Average time:               {avg_different:.2f} ms")
            print(f"  Median time:                {statistics.median(different_slave_times):.2f} ms")
            
            print(f"\nSwitching Overhead:")
            print(f"  Absolute:                   {overhead:+.2f} ms")
            print(f"  Percentage:                 {overhead_pct:+.1f}%")
            
            if overhead > 5:
                print(f"  ⚠ Significant overhead detected when switching slaves!")
            elif overhead > 1:
                print(f"  → Moderate overhead when switching slaves")
            else:
                print(f"  ✓ Minimal overhead - slave switching is efficient")
        else:
            print("Insufficient data to analyze switching overhead")
    
    def print_results(self):
        """Print comprehensive test results"""
        slave_metrics = self.calculate_slave_metrics()
        overall_metrics = self.calculate_overall_metrics(slave_metrics)
        
        print("\n" + "="*80)
        print("OVERALL METRICS (INTERLEAVED SEQUENTIAL TEST)")
        print("="*80)
        print(f"Test Type:                  INTERLEAVED SEQUENTIAL (Single Client)")
        print(f"Total Test Duration:        {overall_metrics.total_duration_seconds:.2f} seconds")
        print(f"Total Slaves:               {overall_metrics.total_slaves}")
        print(f"Total Read Operations:      {overall_metrics.total_reads}")
        print(f"Successful Reads:           {overall_metrics.successful_reads}")
        print(f"Failed Reads:               {overall_metrics.failed_reads}")
        print(f"Overall Success Rate:       {overall_metrics.overall_success_rate:.2f}%")
        print(f"Overall Throughput:         {overall_metrics.overall_requests_per_second:.2f} req/s")
        print(f"Average Response Time:      {overall_metrics.avg_duration_ms:.2f} ms")
        print(f"Median Response Time:       {overall_metrics.median_duration_ms:.2f} ms")
        print(f"Slowest Slave:              Slave {overall_metrics.slowest_slave}")
        print(f"Fastest Slave:              Slave {overall_metrics.fastest_slave}")
        
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
        
        # Switching overhead analysis
        self.analyze_switching_overhead()
        
        # Error summary
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
    """Run the interleaved sequential stress test"""
    
    # CONFIGURATION
    HOST = "192.168.1.100"  # Your Modbus TCP gateway IP
    PORT = 501  # Your Modbus TCP gateway port
    SLAVE_IDS = [1, 2, 3, 4, 5, 6]  # Your 6 slave devices
    REGISTERS = [100, 101, 102, 104, 105, 107, 109, 111]  # Registers to read
    ITERATIONS = 10  # Number of complete cycles through all slaves
    TIMEOUT = 5.0  # Timeout for each read operation (seconds)
    DELAY_BETWEEN_READS = 0.0  # Delay between consecutive reads
    
    # Create and run tester
    tester = ModbusInterleavedTester(
        host=HOST,
        port=PORT,
        slave_ids=SLAVE_IDS,
        registers=REGISTERS,
        iterations=ITERATIONS,
        timeout=TIMEOUT,
        delay_between_reads=DELAY_BETWEEN_READS
    )
    
    tester.run_interleaved_test()
    tester.print_results()


if __name__ == "__main__":
    main()
