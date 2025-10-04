"""
Modbus RTU Interleaved Test - Direct Serial Connection
Tests slave switching performance without gateway
"""

import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict
import statistics

from pymodbus.client import ModbusSerialClient


@dataclass
class ReadResult:
    """Single read operation result"""
    slave_id: int
    iteration: int
    registers: List[int]
    success: bool
    duration_ms: float
    error: Optional[str] = None
    operation_number: int = 0


class ModbusRTUInterleavedTester:
    """Interleaved test - alternates slaves each read"""
    
    def __init__(
        self,
        port: str,
        baudrate: int,
        slave_ids: List[int],
        registers: List[int],
        iterations: int,
        timeout: float = 1.0,
        delay_between_reads: float = 0.0
    ):
        self.port = port
        self.baudrate = baudrate
        self.slave_ids = slave_ids
        self.registers = registers
        self.iterations = iterations
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
        """Run interleaved test"""
        total_operations = len(self.slave_ids) * self.iterations
        
        print(f"\n{'='*80}")
        print(f"DIRECT RTU INTERLEAVED TEST:")
        print(f"  Port: {self.port}")
        print(f"  Baudrate: {self.baudrate}")
        print(f"  Slaves: {len(self.slave_ids)} (IDs: {self.slave_ids})")
        print(f"  Iterations (full cycles): {self.iterations}")
        print(f"  Total operations: {total_operations}")
        print(f"  Registers: {self.registers}")
        print(f"  Pattern: Slave1→Slave2→...→SlaveN, repeat {self.iterations} times")
        print(f"{'='*80}\n")
        
        if not self.connect():
            print("Failed to connect. Aborting test.")
            return
        
        self.start_time = time.time()
        operation_count = 0
        
        try:
            for iteration in range(self.iterations):
                print(f"\nIteration {iteration + 1}/{self.iterations}:")
                
                for slave_id in self.slave_ids:
                    operation_count += 1
                    
                    result = self.read_registers_from_slave(
                        slave_id, iteration, operation_count
                    )
                    self.results.append(result)
                    
                    status = "✓" if result.success else "✗"
                    print(f"  {status} Slave {slave_id}: {result.duration_ms:.1f}ms "
                          f"(op {operation_count}/{total_operations})")
                    
                    if self.delay_between_reads > 0:
                        time.sleep(self.delay_between_reads)
                
                cycle_results = [r for r in self.results if r.iteration == iteration]
                successful = [r for r in cycle_results if r.success]
                cycle_time = sum(r.duration_ms for r in cycle_results)
                print(f"  Cycle: {len(successful)}/{len(cycle_results)} successful, "
                      f"total: {cycle_time:.1f}ms")
        
        finally:
            self.end_time = time.time()
            self.disconnect()
        
        print(f"\n{'='*80}")
        print(f"Test completed in {self.end_time - self.start_time:.2f} seconds")
        print(f"{'='*80}\n")
    
    def analyze_switching_overhead(self):
        """Analyze slave switching overhead"""
        print("\n" + "="*80)
        print("SLAVE SWITCHING ANALYSIS")
        print("="*80)
        
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
            
            print(f"\nReads to SAME slave: {avg_same:.2f}ms avg ({len(same_slave_times)} reads)")
            print(f"Reads to DIFFERENT slave: {avg_different:.2f}ms avg ({len(different_slave_times)} reads)")
            print(f"Switching overhead: {overhead:+.2f}ms ({overhead_pct:+.1f}%)")
    
    def print_results(self):
        """Print comprehensive test results"""
        successful = [r for r in self.results if r.success]
        durations = [r.duration_ms for r in successful]
        
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0
        
        print("\n" + "="*80)
        print("OVERALL METRICS - DIRECT RTU INTERLEAVED TEST")
        print("="*80)
        print(f"Connection: {self.port} @ {self.baudrate} baud")
        print(f"Total Test Duration:        {total_duration:.2f} seconds")
        print(f"Total Reads:                {len(self.results)}")
        print(f"Successful:                 {len(successful)}")
        print(f"Failed:                     {len(self.results) - len(successful)}")
        print(f"Success Rate:               {len(successful)/len(self.results)*100:.2f}%")
        print(f"Throughput:                 {len(successful)/total_duration:.2f} req/s")
        print(f"Avg Response Time:          {statistics.mean(durations):.2f} ms")
        print(f"Median Response Time:       {statistics.median(durations):.2f} ms")
        
        self.analyze_switching_overhead()
        
        print("\n" + "="*80)


def main():
    """Run the direct RTU interleaved test"""
    
    # CONFIGURATION
    PORT = '/dev/ttyACM0'
    BAUDRATE = 19200
    SLAVE_IDS = [1,  3, 4, ]
    REGISTERS = [100, 101]
    ITERATIONS = 20
    TIMEOUT = 1.0
    DELAY_BETWEEN_READS = 0
    
    tester = ModbusRTUInterleavedTester(
        port=PORT,
        baudrate=BAUDRATE,
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
