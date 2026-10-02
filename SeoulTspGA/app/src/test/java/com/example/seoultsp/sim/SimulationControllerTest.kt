package com.example.seoultsp.sim

import com.example.seoultsp.ga.GaConfig
import com.example.seoultsp.ga.MutationMethod
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SimulationControllerTest {

    private fun idleController() = SimulationController(CoroutineScope(Dispatchers.Unconfined))

    @Test
    fun startsReadyWithInitialGeneration() {
        val c = idleController()
        assertEquals(SimStatus.Ready, c.status)
        assertEquals(1, c.history.size)
        assertEquals(0, c.history.single().generation)
        assertEquals(0, c.bestTour.first())
        assertEquals(c.attractions.indices.toList(), c.bestTour.sorted())
    }

    @Test
    fun stepOnce_advancesOneGenerationAndLocksParameters() {
        val c = idleController()
        c.stepOnce()
        assertEquals(SimStatus.Paused, c.status)
        assertEquals(2, c.history.size)
        assertFalse(c.canEditParameters)

        val before = c.config
        c.updateConfig { it.copy(populationSize = 200) }
        assertEquals("일시정지 중에는 파라미터가 바뀌면 안 됩니다", before, c.config)
    }

    @Test
    fun reset_archivesProgressedRunForComparison() {
        val c = idleController()
        assertNull(c.previousRun)
        repeat(10) { c.stepOnce() }
        c.reset()
        assertNotNull(c.previousRun)
        val record = c.previousRun!!
        assertEquals(11, record.bestCurve.size)
        assertEquals(SimStatus.Ready, c.status)
        assertEquals(1, c.history.size)
        assertTrue(c.canEditParameters)
    }

    @Test
    fun updateConfig_rebuildsPopulationAndSanitizes() {
        val c = idleController()
        c.updateConfig { it.copy(populationSize = 10_000, mutation = MutationMethod.Swap) }
        assertEquals(GaConfig.POPULATION_RANGE.last, c.config.populationSize)
        assertEquals(MutationMethod.Swap, c.config.mutation)
        assertEquals(1, c.history.size)
    }

    @Test
    fun bestCostNeverIncreases() {
        val c = idleController()
        var previous = c.bestCost
        repeat(100) {
            c.stepOnce()
            assertTrue(c.bestCost <= previous)
            previous = c.bestCost
        }
    }

    @Test
    fun playPause_runsToCompletion() = runBlocking {
        val c = SimulationController(this, GaConfig(generations = 60))
        c.speed = SimSpeed.Max
        c.playPause()
        assertEquals(SimStatus.Running, c.status)
        withTimeout(10_000) {
            while (c.status == SimStatus.Running) delay(5)
        }
        assertEquals(SimStatus.Finished, c.status)
        assertEquals(61, c.history.size)
        assertEquals((0..60).toList(), c.history.map { it.generation })
    }

    @Test
    fun pause_stopsTheLoop() = runBlocking {
        val c = SimulationController(this, GaConfig(generations = 2000))
        c.speed = SimSpeed.Normal
        c.playPause()
        delay(120)
        c.playPause()
        assertEquals(SimStatus.Paused, c.status)
        val frozen = c.history.size
        delay(150)
        assertEquals(frozen, c.history.size)
        assertTrue(frozen in 2 until 2001)
    }

    @Test
    fun normalizeTour_startsAtZeroWithCanonicalDirection() {
        assertEquals(listOf(0, 1, 2, 3), SimulationController.normalizeTour(listOf(2, 3, 0, 1)))
        assertEquals(listOf(0, 1, 2, 3), SimulationController.normalizeTour(listOf(3, 2, 1, 0)))
    }
}
