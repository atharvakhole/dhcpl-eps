"""
Modbus RS485 Sequential Stress Test
Tests sequential read operations across multiple slaves through TCP gateway
Uses a SINGLE client with slave ID specified per read operation
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
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


class ModbusSequentialTester:
    """Sequential stress test with single Modbus TCP client"""
    
    def __init__(
        self,
        host: str,
        port: int,
        slave_ids: List[int],
        registers: List[int],
        iterations_per_slave: int,
        timeout: float = 5.0,
        delay_between_reads: float = 0.0
    ):
        self.host = host
        self.port = port
        self.slave_ids = slave_ids
        self.registers = registers
        self.iterations_per_slave = iterations_per_slave
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
        iteration: int
    ) -> ReadResult:
        """Read registers from a specific slave using the shared client"""
        start = time.time()
        
        try:
            # Read holding registers with slave_id specified here
            response = self.client.read_holding_registers(
                address=min(self.registers),
                count=max(self.registers) - min(self.registers) + 1,
                slave=slave_id  # Slave ID specified per read
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
            
            # Extract only the registers we care about
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
        print(f"Starting SEQUENTIAL stress test:")
        print(f"  Slaves: {len(self.slave_ids)} (IDs: {self.slave_ids})")
        print(f"  Iterations per slave: {self.iterations_per_slave}")
        print(f"  Total operations: {len(self.slave_ids) * self.iterations_per_slave}")
        print(f"  Registers to read: {self.registers}")
        print(f"  Target: {self.host}:{self.port}")
        print(f"  Delay between reads: {self.delay_between_reads}s")
        print(f"  Using: SINGLE shared client")
        print(f"{'='*80}\n")
        
        if not self.connect():
            print("Failed to connect. Aborting test.")
            return
        
        self.start_time = time.time()
        total_operations = len(self.slave_ids) * self.iterations_per_slave
        operation_count = 0
        
        try:
            # Sequential loop: for each slave, do all iterations
            for slave_id in self.slave_ids:
                print(f"\nTesting Slave {slave_id}...")
                
                for iteration in range(self.iterations_per_slave):
                    operation_count += 1
                    
                    # Perform read
                    result = self.read_registers_from_slave(slave_id, iteration)
                    self.results.append(result)
                    
                    # Progress indicator
                    if iteration % 10 == 0 or iteration == self.iterations_per_slave - 1:
                        success_count = sum(1 for r in self.results if r.success and r.slave_id == slave_id)
                        print(f"  Iteration {iteration + 1}/{self.iterations_per_slave} "
                              f"({success_count} successful, "
                              f"{result.duration_ms:.1f}ms)")
                    
                    # Optional delay between reads
                    if self.delay_between_reads > 0:
                        time.sleep(self.delay_between_reads)
                
                # Summary for this slave
                slave_results = [r for r in self.results if r.slave_id == slave_id]
                successful = [r for r in slave_results if r.success]
                print(f"  ✓ Slave {slave_id} complete: "
                      f"{len(successful)}/{len(slave_results)} successful")
        
        finally:
            self.end_time = time.time()
            self.disconnect()
        
        print(f"\n{'='*80}")
        print(f"Test completed in {self.end_time - self.start_time:.2f} seconds")
        print(f"{'='*80}\n")
    
    def calculate_slave_metrics(self) -> Dict[int, SlaveMetrics]:
        """Calculate metrics per slave"""
        slave_results = defaultdict(list)
        
        # Group results by slave_id
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
    
    def print_results(self):
        """Print comprehensive test results"""
        slave_metrics = self.calculate_slave_metrics()
        overall_metrics = self.calculate_overall_metrics(slave_metrics)
        
        print("\n" + "="*80)
        print("OVERALL METRICS (SEQUENTIAL TEST)")
        print("="*80)
        print(f"Test Type:                  SEQUENTIAL (Single Client)")
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
            print(f"  Total Time for Slave:     {metrics.total_duration_ms / 1000:.2f} seconds")
            print(f"  Effective Throughput:     {metrics.requests_per_second:.2f} req/s")
        
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
        
        # Performance insights
        print("\n" + "="*80)
        print("PERFORMANCE INSIGHTS")
        print("="*80)
        
        if overall_metrics.overall_success_rate == 100:
            print("✓ All operations successful - system is stable under sequential load")
        else:
            print(f"⚠ {overall_metrics.failed_reads} failed operations - investigate errors above")
        
        time_per_read = overall_metrics.avg_duration_ms
        theoretical_max_rps = 1000 / time_per_read if time_per_read > 0 else 0
        
        print(f"\nSequential Performance:")
        print(f"  Average time per read:      {time_per_read:.2f} ms")
        print(f"  Theoretical max (1 slave):  {theoretical_max_rps:.2f} req/s")
        print(f"  Actual throughput:          {overall_metrics.overall_requests_per_second:.2f} req/s")
        print(f"  Efficiency:                 {(overall_metrics.overall_requests_per_second / theoretical_max_rps * 100):.1f}%")
        
        print("\n" + "="*80)



def test_multi_slave_cache_behavior(host, port, slave_ids):
    """Test if gateway caches ALL slaves or just the requested one"""
    client = ModbusTcpClient(host, port, timeout=5.0)
    client.connect()
    
    print("\n" + "="*80)
    print("MULTI-SLAVE GATEWAY CACHE BEHAVIOR TEST")
    print("="*80)
    print(f"Testing slaves: {slave_ids}")
    
    # ========================================================================
    # Test 1: Does reading Slave 1 cache ALL other slaves?
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 1: Cache Propagation Test")
    print("Does reading Slave 1 trigger gateway to cache ALL slaves?")
    print("="*80)
    
    # Wait to ensure cache is cold
    print("\nWaiting 5s to ensure cache is cold...")
    time.sleep(5)
    
    # Read Slave 1 (should be cache miss, trigger gateway poll)
    print(f"\nReading Slave {slave_ids[0]} (should trigger gateway poll)...")
    start = time.time()
    response = client.read_holding_registers(100, 8, slave=slave_ids[0])
    duration1 = (time.time() - start) * 1000
    print(f"  Slave {slave_ids[0]}: {duration1:.2f}ms [CACHE MISS - GATEWAY POLLS]")
    
    # Immediately read other slaves - are they cached?
    print(f"\nImmediately reading other slaves (are they cached?)...")
    results = []
    for slave_id in slave_ids[1:]:
        start = time.time()
        response = client.read_holding_registers(100, 8, slave=slave_id)
        duration = (time.time() - start) * 1000
        results.append(duration)
        
        cache_status = "CACHE HIT" if duration < 10 else "CACHE MISS"
        print(f"  Slave {slave_id}: {duration:.2f}ms [{cache_status}]")
    
    avg_other_slaves = statistics.mean(results)
    
    print(f"\nConclusion:")
    if avg_other_slaves < 10:
        print(f"  ✓ Other slaves averaged {avg_other_slaves:.2f}ms (cache hits)")
        print(f"  → Gateway polls ALL slaves when any slave is requested")
        print(f"  → You can read all {len(slave_ids)} slaves in ~{duration1:.0f}ms")
    else:
        print(f"  ✗ Other slaves averaged {avg_other_slaves:.2f}ms (cache misses)")
        print(f"  → Gateway only caches the requested slave")
        print(f"  → Reading all {len(slave_ids)} slaves takes ~{(duration1 + sum(results)):.0f}ms")
    
    # ========================================================================
    # Test 2: Round-robin rapid fire (switching every read)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 2: Round-Robin Switching Test")
    print("Rapidly cycling through slaves: 1→2→3→4→5→6→1→2...")
    print("="*80)
    
    # Wait for cache to expire
    print("\nWaiting 5s for cache to expire...")
    time.sleep(5)
    
    print(f"\nReading 3 complete cycles through all {len(slave_ids)} slaves...")
    times_by_slave = {slave_id: [] for slave_id in slave_ids}
    
    for cycle in range(3):
        print(f"\n  Cycle {cycle + 1}:")
        for slave_id in slave_ids:
            start = time.time()
            response = client.read_holding_registers(100, 8, slave=slave_id)
            duration = (time.time() - start) * 1000
            times_by_slave[slave_id].append(duration)
            
            cache_status = "HIT" if duration < 10 else "MISS"
            print(f"    Slave {slave_id}: {duration:.2f}ms [{cache_status}]")
    
    print(f"\nAverage times per slave across 3 cycles:")
    for slave_id, times in times_by_slave.items():
        avg = statistics.mean(times)
        print(f"  Slave {slave_id}: {avg:.2f}ms")
    
    # ========================================================================
    # Test 3: Slave switching overhead
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 3: Slave Switching Overhead")
    print("Compare: same slave repeated vs alternating slaves")
    print("="*80)
    
    # Wait for cache to expire
    time.sleep(5)
    
    # Same slave repeated (measure cache effectiveness)
    print(f"\nReading Slave {slave_ids[0]} 10 times rapidly...")
    same_slave_times = []
    for i in range(10):
        start = time.time()
        response = client.read_holding_registers(100, 8, slave=slave_ids[0])
        duration = (time.time() - start) * 1000
        same_slave_times.append(duration)
    
    print(f"  First read: {same_slave_times[0]:.2f}ms (cache miss)")
    print(f"  Subsequent reads avg: {statistics.mean(same_slave_times[1:]):.2f}ms (cache hits)")
    
    # Wait for cache to expire
    time.sleep(5)
    
    # Alternating between two slaves
    print(f"\nAlternating between Slave {slave_ids[0]} and Slave {slave_ids[1]} 10 times...")
    alternating_times = []
    for i in range(10):
        slave_id = slave_ids[i % 2]
        start = time.time()
        response = client.read_holding_registers(100, 8, slave=slave_id)
        duration = (time.time() - start) * 1000
        alternating_times.append(duration)
        print(f"  Slave {slave_id}: {duration:.2f}ms")
    
    print(f"\nComparison:")
    print(f"  Same slave (with cache): {statistics.mean(same_slave_times):.2f}ms avg")
    print(f"  Alternating slaves: {statistics.mean(alternating_times):.2f}ms avg")
    
    overhead = statistics.mean(alternating_times) - statistics.mean(same_slave_times)
    print(f"  Switching overhead: {overhead:+.2f}ms ({(overhead/statistics.mean(same_slave_times)*100):+.1f}%)")
    
    # ========================================================================
    # Test 4: Sequential blocking (all slaves one after another)
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 4: Sequential Blocking Test")
    print("Read all 6 slaves sequentially (realistic API pattern)")
    print("="*80)
    
    for attempt in range(2):
        print(f"\nAttempt {attempt + 1}:")
        
        # Wait for cache to expire
        if attempt > 0:
            time.sleep(5)
        
        total_start = time.time()
        times = []
        
        for slave_id in slave_ids:
            start = time.time()
            response = client.read_holding_registers(100, 8, slave=slave_id)
            duration = (time.time() - start) * 1000
            times.append(duration)
            
            cache_status = "HIT" if duration < 10 else "MISS"
            print(f"  Slave {slave_id}: {duration:.2f}ms [{cache_status}]")
        
        total_duration = (time.time() - total_start) * 1000
        print(f"  Total time for all {len(slave_ids)} slaves: {total_duration:.2f}ms")
    
    # ========================================================================
    # Test 5: Cache TTL per slave
    # ========================================================================
    print("\n" + "="*80)
    print("TEST 5: Individual Slave Cache TTL")
    print("Finding cache expiration time per slave")
    print("="*80)
    
    for slave_id in slave_ids[:2]:  # Test first 2 slaves only
        print(f"\nTesting Slave {slave_id}:")
        
        # Prime cache
        time.sleep(5)
        response = client.read_holding_registers(100, 8, slave=slave_id)
        print(f"  Primed cache")
        
        # Test at intervals
        test_delays = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        for delay in test_delays:
            time.sleep(delay)
            start = time.time()
            response = client.read_holding_registers(100, 8, slave=slave_id)
            duration = (time.time() - start) * 1000
            
            cache_status = "HIT" if duration < 10 else "MISS"
            print(f"  After {delay:.1f}s: {duration:.2f}ms [{cache_status}]")
            
            if cache_status == "MISS":
                print(f"  → Cache TTL for Slave {slave_id}: ~{delay:.1f}s")
                break
    
    client.close()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)




def test_cache_behavior(host, port, slave_id):
    """Test if gateway caches responses"""
    client = ModbusTcpClient(host, port, timeout=5.0)
    client.connect()
    
    print("\n" + "="*80)
    print("GATEWAY CACHE BEHAVIOR TEST")
    print("="*80)
    
    # Test 1: Rapid fire (should hit cache)
    print("\nTest 1: 10 rapid requests to same slave")
    times = []
    for i in range(10):
        start = time.time()
        response = client.read_holding_registers(100, 8, slave=slave_id)
        duration = (time.time() - start) * 1000
        times.append(duration)
        print(f"  Request {i+1}: {duration:.2f}ms")
    
    print(f"\nRapid fire average: {statistics.mean(times):.2f}ms")
    
    # Test 2: With pauses (should miss cache)
    print("\nTest 2: 10 requests with 2s pauses")
    times = []
    for i in range(10):
        time.sleep(2)  # Wait for cache to expire
        start = time.time()
        response = client.read_holding_registers(100, 8, slave=slave_id)
        duration = (time.time() - start) * 1000
        times.append(duration)
        print(f"  Request {i+1}: {duration:.2f}ms")
    
    print(f"\nWith pauses average: {statistics.mean(times):.2f}ms")
    
    client.close()

# Run it

def main():
    """Run the sequential stress test"""
    
    # CONFIGURATION
    HOST = "192.168.1.100"  # Your Modbus TCP gateway IP
    PORT = 501  # Your Modbus TCP gateway port
    SLAVE_IDS = [1, 2, 3, 4, 5, 6]  # Your 6 slave devices
    REGISTERS = [100, 101, 102, 104, 105, 107, 109, 111]  # Registers to read
    ITERATIONS_PER_SLAVE = 10 # How many times to read from each slave
    TIMEOUT = 5.0  # Timeout for each read operation (seconds)
    DELAY_BETWEEN_READS = 0.0  # Delay between consecutive reads (0 = no delay)
    
    # Create and run tester
    tester = ModbusSequentialTester(
        host=HOST,
        port=PORT,
        slave_ids=SLAVE_IDS,
        registers=REGISTERS,
        iterations_per_slave=ITERATIONS_PER_SLAVE,
        timeout=TIMEOUT,
        delay_between_reads=DELAY_BETWEEN_READS
    )
    
    # tester.run_sequential_test()
    # tester.print_results()
    # test_cache_behavior("192.168.1.100", 501, 1)
    # Run the comprehensive test
    test_multi_slave_cache_behavior(
        host="192.168.1.100",
        port=501,
        slave_ids=[1, 2, 3, 4, 5, 6]
    )


if __name__ == "__main__":
    main()
