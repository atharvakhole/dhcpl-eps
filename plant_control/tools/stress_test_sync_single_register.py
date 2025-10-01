"""
Modbus RS485 Sequential Test - INDIVIDUAL REGISTER READS
Tests sequential reads with one register per request
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict
import statistics

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException


@dataclass
class RegisterReadResult:
    """Single register read operation result"""
    slave_id: int
    register: int
    iteration: int
    value: Optional[int]
    success: bool
    duration_ms: float
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class TagReadResult:
    """Complete tag read (all registers) result"""
    slave_id: int
    iteration: int
    registers: Dict[int, int]
    success: bool
    duration_ms: float
    failed_registers: List[int]


@dataclass
class SlaveMetrics:
    """Metrics for one slave"""
    slave_id: int
    total_tag_reads: int
    successful_tag_reads: int
    failed_tag_reads: int
    total_register_reads: int
    successful_register_reads: int
    failed_register_reads: int
    success_rate: float
    avg_tag_duration_ms: float
    avg_register_duration_ms: float
    median_tag_duration_ms: float
    median_register_duration_ms: float
    min_register_duration_ms: float
    max_register_duration_ms: float


@dataclass
class OverallMetrics:
    """System-wide metrics"""
    total_slaves: int
    total_tag_reads: int
    total_register_reads: int
    successful_tag_reads: int
    successful_register_reads: int
    failed_register_reads: int
    overall_success_rate: float
    total_duration_seconds: float
    tags_per_second: float
    registers_per_second: float
    avg_tag_duration_ms: float
    avg_register_duration_ms: float


class ModbusSequentialIndividualTester:
    """Sequential stress test - reads one register at a time"""
    
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
        self.register_results: List[RegisterReadResult] = []
        self.tag_results: List[TagReadResult] = []
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
    
    def read_single_register(
        self,
        slave_id: int,
        register: int,
        iteration: int
    ) -> RegisterReadResult:
        """Read a SINGLE register"""
        start = time.time()
        
        try:
            # Read only 1 register
            response = self.client.read_holding_registers(
                address=register,
                count=1,
                slave=slave_id
            )
            
            duration_ms = (time.time() - start) * 1000
            
            if response.isError():
                return RegisterReadResult(
                    slave_id=slave_id,
                    register=register,
                    iteration=iteration,
                    value=None,
                    success=False,
                    duration_ms=duration_ms,
                    error=str(response)
                )
            
            return RegisterReadResult(
                slave_id=slave_id,
                register=register,
                iteration=iteration,
                value=response.registers[0],
                success=True,
                duration_ms=duration_ms
            )
            
        except ModbusException as e:
            duration_ms = (time.time() - start) * 1000
            return RegisterReadResult(
                slave_id=slave_id,
                register=register,
                iteration=iteration,
                value=None,
                success=False,
                duration_ms=duration_ms,
                error=f"ModbusException: {str(e)}"
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            return RegisterReadResult(
                slave_id=slave_id,
                register=register,
                iteration=iteration,
                value=None,
                success=False,
                duration_ms=duration_ms,
                error=f"Exception: {str(e)}"
            )
    
    def read_tag_from_slave(
        self,
        slave_id: int,
        iteration: int
    ) -> TagReadResult:
        """Read all registers for one tag (multiple individual reads)"""
        tag_start = time.time()
        register_values = {}
        failed_registers = []
        
        for register in self.registers:
            result = self.read_single_register(slave_id, register, iteration)
            self.register_results.append(result)
            
            if result.success:
                register_values[register] = result.value
            else:
                failed_registers.append(register)
            
            # Delay between individual register reads
            if self.delay_between_reads > 0:
                time.sleep(self.delay_between_reads)
        
        tag_duration_ms = (time.time() - tag_start) * 1000
        
        return TagReadResult(
            slave_id=slave_id,
            iteration=iteration,
            registers=register_values,
            success=len(failed_registers) == 0,
            duration_ms=tag_duration_ms,
            failed_registers=failed_registers
        )
    
    def run_sequential_test(self):
        """Run all read operations sequentially"""
        total_register_reads = len(self.slave_ids) * self.iterations_per_slave * len(self.registers)
        
        print(f"\n{'='*80}")
        print(f"Starting SEQUENTIAL stress test - INDIVIDUAL REGISTER READS:")
        print(f"  Slaves: {len(self.slave_ids)} (IDs: {self.slave_ids})")
        print(f"  Iterations per slave: {self.iterations_per_slave}")
        print(f"  Registers per tag: {len(self.registers)}")
        print(f"  Total tag reads: {len(self.slave_ids) * self.iterations_per_slave}")
        print(f"  Total register reads: {total_register_reads}")
        print(f"  Registers: {self.registers}")
        print(f"  Target: {self.host}:{self.port}")
        print(f"  Delay between reads: {self.delay_between_reads}s")
        print(f"  Mode: ONE REGISTER PER REQUEST")
        print(f"{'='*80}\n")
        
        if not self.connect():
            print("Failed to connect. Aborting test.")
            return
        
        self.start_time = time.time()
        
        try:
            for slave_id in self.slave_ids:
                print(f"\nTesting Slave {slave_id}...")
                
                for iteration in range(self.iterations_per_slave):
                    tag_result = self.read_tag_from_slave(slave_id, iteration)
                    self.tag_results.append(tag_result)
                    
                    if iteration % 5 == 0 or iteration == self.iterations_per_slave - 1:
                        success_count = sum(1 for r in self.tag_results 
                                          if r.success and r.slave_id == slave_id)
                        print(f"  Iteration {iteration + 1}/{self.iterations_per_slave}: "
                              f"{len(tag_result.registers)}/{len(self.registers)} registers, "
                              f"{tag_result.duration_ms:.1f}ms total")
                
                slave_tags = [r for r in self.tag_results if r.slave_id == slave_id]
                successful = [r for r in slave_tags if r.success]
                print(f"  ✓ Slave {slave_id} complete: {len(successful)}/{len(slave_tags)} successful tags")
        
        finally:
            self.end_time = time.time()
            self.disconnect()
        
        print(f"\n{'='*80}")
        print(f"Test completed in {self.end_time - self.start_time:.2f} seconds")
        print(f"{'='*80}\n")
    
    def calculate_slave_metrics(self) -> Dict[int, SlaveMetrics]:
        """Calculate metrics per slave"""
        metrics = {}
        
        for slave_id in self.slave_ids:
            slave_tags = [r for r in self.tag_results if r.slave_id == slave_id]
            slave_registers = [r for r in self.register_results if r.slave_id == slave_id]
            
            successful_tags = [r for r in slave_tags if r.success]
            failed_tags = [r for r in slave_tags if not r.success]
            
            successful_registers = [r for r in slave_registers if r.success]
            failed_registers = [r for r in slave_registers if not r.success]
            
            tag_durations = [r.duration_ms for r in slave_tags]
            register_durations = [r.duration_ms for r in successful_registers]
            
            if tag_durations and register_durations:
                metrics[slave_id] = SlaveMetrics(
                    slave_id=slave_id,
                    total_tag_reads=len(slave_tags),
                    successful_tag_reads=len(successful_tags),
                    failed_tag_reads=len(failed_tags),
                    total_register_reads=len(slave_registers),
                    successful_register_reads=len(successful_registers),
                    failed_register_reads=len(failed_registers),
                    success_rate=len(successful_tags) / len(slave_tags) * 100,
                    avg_tag_duration_ms=statistics.mean(tag_durations),
                    avg_register_duration_ms=statistics.mean(register_durations),
                    median_tag_duration_ms=statistics.median(tag_durations),
                    median_register_duration_ms=statistics.median(register_durations),
                    min_register_duration_ms=min(register_durations),
                    max_register_duration_ms=max(register_durations)
                )
        
        return metrics
    
    def calculate_overall_metrics(self) -> OverallMetrics:
        """Calculate overall system metrics"""
        successful_tags = [r for r in self.tag_results if r.success]
        successful_registers = [r for r in self.register_results if r.success]
        failed_registers = [r for r in self.register_results if not r.success]
        
        tag_durations = [r.duration_ms for r in self.tag_results]
        register_durations = [r.duration_ms for r in successful_registers]
        
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        return OverallMetrics(
            total_slaves=len(self.slave_ids),
            total_tag_reads=len(self.tag_results),
            total_register_reads=len(self.register_results),
            successful_tag_reads=len(successful_tags),
            successful_register_reads=len(successful_registers),
            failed_register_reads=len(failed_registers),
            overall_success_rate=len(successful_tags) / len(self.tag_results) * 100 if self.tag_results else 0,
            total_duration_seconds=total_duration,
            tags_per_second=len(successful_tags) / total_duration if total_duration > 0 else 0,
            registers_per_second=len(successful_registers) / total_duration if total_duration > 0 else 0,
            avg_tag_duration_ms=statistics.mean(tag_durations) if tag_durations else 0,
            avg_register_duration_ms=statistics.mean(register_durations) if register_durations else 0
        )
    
    def print_results(self):
        """Print comprehensive test results"""
        slave_metrics = self.calculate_slave_metrics()
        overall_metrics = self.calculate_overall_metrics()
        
        print("\n" + "="*80)
        print("OVERALL METRICS - INDIVIDUAL REGISTER READS")
        print("="*80)
        print(f"Test Type:                  SEQUENTIAL (Individual Registers)")
        print(f"Total Test Duration:        {overall_metrics.total_duration_seconds:.2f} seconds")
        print(f"Total Slaves:               {overall_metrics.total_slaves}")
        print(f"\nTag-Level Metrics:")
        print(f"  Total Tag Reads:          {overall_metrics.total_tag_reads}")
        print(f"  Successful Tags:          {overall_metrics.successful_tag_reads}")
        print(f"  Tag Success Rate:         {overall_metrics.overall_success_rate:.2f}%")
        print(f"  Tags per Second:          {overall_metrics.tags_per_second:.2f}")
        print(f"  Avg Tag Duration:         {overall_metrics.avg_tag_duration_ms:.2f} ms")
        print(f"\nRegister-Level Metrics:")
        print(f"  Total Register Reads:     {overall_metrics.total_register_reads}")
        print(f"  Successful Registers:     {overall_metrics.successful_register_reads}")
        print(f"  Failed Registers:         {overall_metrics.failed_register_reads}")
        print(f"  Registers per Second:     {overall_metrics.registers_per_second:.2f}")
        print(f"  Avg Register Duration:    {overall_metrics.avg_register_duration_ms:.2f} ms")
        
        print("\n" + "="*80)
        print("PER-SLAVE METRICS")
        print("="*80)
        for slave_id in sorted(slave_metrics.keys()):
            m = slave_metrics[slave_id]
            print(f"\nSlave {slave_id}:")
            print(f"  Tag reads:                {m.successful_tag_reads}/{m.total_tag_reads} successful")
            print(f"  Register reads:           {m.successful_register_reads}/{m.total_register_reads} successful")
            print(f"  Success rate:             {m.success_rate:.2f}%")
            print(f"  Avg tag duration:         {m.avg_tag_duration_ms:.2f} ms")
            print(f"  Avg register duration:    {m.avg_register_duration_ms:.2f} ms")
            print(f"  Register range:           {m.min_register_duration_ms:.2f} - {m.max_register_duration_ms:.2f} ms")
        
        # Error summary
        failed = [r for r in self.register_results if not r.success]
        if failed:
            print("\n" + "="*80)
            print("ERROR SUMMARY")
            print("="*80)
            error_counts = defaultdict(int)
            for result in failed:
                error_counts[result.error] += 1
            
            for error, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"  {count}x: {error}")
        
        print("\n" + "="*80)
        print("PERFORMANCE COMPARISON")
        print("="*80)
        registers_per_tag = len(self.registers)
        print(f"Reading {registers_per_tag} registers individually vs bulk:")
        print(f"  Time per tag (individual): {overall_metrics.avg_tag_duration_ms:.2f} ms")
        print(f"  Time per register:         {overall_metrics.avg_register_duration_ms:.2f} ms")
        print(f"  Overhead per tag:          {overall_metrics.avg_tag_duration_ms - overall_metrics.avg_register_duration_ms:.2f} ms")
        print(f"  Efficiency:                {(overall_metrics.avg_register_duration_ms / overall_metrics.avg_tag_duration_ms * registers_per_tag * 100):.1f}%")
        
        print("\n" + "="*80)


def main():
    """Run the sequential individual register test"""
    
    # CONFIGURATION
    HOST = "192.168.1.100"
    PORT = 501
    SLAVE_IDS = [1, 2, 3, 4, 5, 6]
    REGISTERS = [100, 101, 102, 104, 105, 107, 109, 111]
    ITERATIONS_PER_SLAVE = 10
    TIMEOUT = 5.0
    DELAY_BETWEEN_READS = 0.0
    
    tester = ModbusSequentialIndividualTester(
        host=HOST,
        port=PORT,
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
